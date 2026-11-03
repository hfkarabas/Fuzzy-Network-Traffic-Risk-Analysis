"""Local FastAPI HTTP adapter. Start with Uvicorn bound to 127.0.0.1."""
from contextlib import asynccontextmanager
from typing import Literal,Annotated,Any
import logging
import html
import ipaddress
import secrets
from fastapi import FastAPI,Request,Depends,Header,HTTPException,Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,FileResponse,HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,ConfigDict,Field,StrictFloat
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .service import WebService,ROOT
from ..realtime.monitor import Monitor
from ..realtime.capture import CaptureError

Number=Annotated[StrictFloat,Field(ge=0,allow_inf_nan=False)]

class FlowFeatures(BaseModel):
    model_config=ConfigDict(extra='forbid')
    rate:Number|None=Field(alias=' Flow Packets/s',description='Paket yoğunluğu, paket/saniye')
    volume:Number|None=Field(alias=' Total Fwd Packets',description='İleri yön paket sayısı, paket')
    size:Number|None=Field(alias=' Packet Length Mean',description='Ortalama paket boyutu, bayt')
    variation:Number|None=Field(alias=' Bwd Packet Length Std',description='Geri yön boyut standart sapması, bayt')
    balance:Number|None=Field(alias=' Down/Up Ratio',description='Tam sayı olarak dışa aktarılmış geri/ileri oranı')

class AnalyzeRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    features:FlowFeatures
    policy:Literal['Sensitive','Balanced','Conservative']='Balanced'

class MonitorStart(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode:Literal['capture','replay']='capture'
    interface:Annotated[str,Field(min_length=1,max_length=512)]|None=None
    authorized:Literal[True]

class AnalyzeResponse(BaseModel):
    status:Literal['ok','invalid_input','no_rule_activation']
    risk_score:Annotated[float,Field(ge=0,le=100)]|None
    risk_level:Literal['Low','Medium','High','Critical']|None
    risk_level_tr:str|None
    alert:bool|None
    alert_policy:dict[str,Any]
    model_id:str
    model_version:str
    membership_degrees:dict[str,dict[str,float]]
    activated_rules:list[dict[str,Any]]
    explanation:str
    explanation_tr:str
    explanation_data:dict[str,Any]
    input_values:dict[str,float|None]
    input_positions:dict[str,float]
    validation_errors:list[dict[str,str]]

def create_app(root=ROOT,monitor_factory=Monitor):
    @asynccontextmanager
    async def lifespan(app):
        app.state.service=WebService(root)
        app.state.monitor=monitor_factory(app.state.service)
        try: yield
        finally:
            from starlette.concurrency import run_in_threadpool
            await run_in_threadpool(app.state.monitor.stop)

    app=FastAPI(title='Fuzzy Network Risk · Yerel API',version='1.0.0',lifespan=lifespan,
                docs_url=None,redoc_url=None,description='Eğitim amaçlı, dondurulmuş Mamdani çıkarımı. Puan saldırı olasılığı değildir.')
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver','[::1]'])

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        errors=[{'field':'.'.join(map(str,e['loc'][1:])),'message':'Eksik, tanınmayan veya geçersiz değer. Sayılar sonlu ve sıfırdan küçük olmamalı.'} for e in exc.errors()]
        return JSONResponse(status_code=422,content={'status':'invalid_input','risk_score':None,'risk_level':None,'alert':None,
                                                    'activated_rules':[],'membership_degrees':{},'validation_errors':errors,
                                                    'explanation_tr':'Girdi doğrulanamadı. Risk puanı üretilmedi.'})

    @app.exception_handler(Exception)
    async def unexpected_error(request,exc):
        logging.getLogger('fuzzy.web').exception('Local inference request failed')
        return JSONResponse(status_code=500,content={'status':'error','message':'İşlem tamamlanamadı. Yerel sunucu günlüklerini kontrol edin.'})

    @app.get('/api/health',tags=['System'])
    def health(request:Request): return {'status':'ok','model_loaded':True,'model_id':request.app.state.service.engine.model_id,'local_only':True,
                                        'configuration_version':request.app.state.service.model['configuration_version']}

    @app.get('/api/model',tags=['System'])
    def model(request:Request): return request.app.state.service.model

    @app.get('/api/policies',tags=['Inference'])
    def policies(request:Request): return {'default':'Balanced','policies':request.app.state.service.policy_list()}

    @app.post('/api/analyze',tags=['Inference'],response_model=AnalyzeResponse,responses={422:{'description':'Explicit validation abstention; null score/category/alert'}})
    def analyze(body:AnalyzeRequest,request:Request):
        return request.app.state.service.analyze(body.features.model_dump(by_alias=True),body.policy)

    @app.get('/api/examples',tags=['Data'])
    def examples(request:Request):
        service=request.app.state.service
        return {'examples':service.examples,'scope':service.catalog['scope'],'unavailable_categories':service.catalog['unavailable_categories'],
                'reference_policy':'Balanced','curated_not_representative':True}

    @app.get('/api/evaluation',tags=['Data'])
    def evaluation(request:Request): return request.app.state.service.evaluation

    def local_monitor(request:Request):
        try: local=bool(request.client and ipaddress.ip_address(request.client.host).is_loopback)
        except ValueError: local=False
        origin=request.headers.get('origin')
        allowed={'http://127.0.0.1:5173','http://localhost:5173','http://[::1]:5173',
                 'http://127.0.0.1:8000','http://localhost:8000','http://[::1]:8000'}
        if not local or (origin and origin not in allowed) or request.headers.get('sec-fetch-site')=='cross-site':
            raise HTTPException(403,detail='İzleme yalnızca yerel uygulamadan kullanılabilir.')

    def control_monitor(request:Request,x_monitor_token:Annotated[str|None,Header()]=None):
        local_monitor(request)
        if not x_monitor_token or not secrets.compare_digest(x_monitor_token.encode(),request.app.state.monitor.token.encode()):
            raise HTTPException(403,detail='Yerel izleme kontrol anahtarı eksik; sayfayı yenileyin.')

    @app.exception_handler(CaptureError)
    async def capture_error(request,exc):
        code=409 if exc.code=='already_running' else 422 if exc.code.startswith('invalid_') else 403 if exc.code=='permission_denied' else 503
        return JSONResponse(status_code=code,content={'error':{'code':exc.code,'message':str(exc)}})

    @app.get('/api/live/interfaces',dependencies=[Depends(local_monitor)],tags=['Live'])
    def live_interfaces(request:Request): return request.app.state.monitor.discovery()

    @app.get('/api/live/status',dependencies=[Depends(local_monitor)],tags=['Live'])
    def live_status(request:Request,policy:Literal['Sensitive','Balanced','Conservative']='Balanced',limit:Annotated[int,Query(ge=1,le=200)]=50):
        return request.app.state.monitor.snapshot(policy,limit)

    @app.get('/api/live/flows',dependencies=[Depends(local_monitor)],tags=['Live'])
    def live_flows(request:Request,policy:Literal['Sensitive','Balanced','Conservative']='Balanced',limit:Annotated[int,Query(ge=1,le=200)]=50):
        result=request.app.state.monitor.snapshot(policy,limit)
        return {'session_id':result['session_id'],'flows':result['flows']}

    @app.get('/api/live/stats',dependencies=[Depends(local_monitor)],tags=['Live'])
    def live_stats(request:Request,policy:Literal['Sensitive','Balanced','Conservative']='Balanced'):
        result=request.app.state.monitor.snapshot(policy,1)
        return {key:result[key] for key in ['state','running','active_flows','counts','risk_distribution','policy','session_id']}

    @app.get('/api/live/errors',dependencies=[Depends(local_monitor)],tags=['Live'])
    def live_errors(request:Request): return {'errors':request.app.state.monitor.snapshot(limit=1)['errors']}

    @app.post('/api/live/start',dependencies=[Depends(control_monitor)],tags=['Live'])
    def live_start(body:MonitorStart,request:Request): return request.app.state.monitor.start(body.mode,body.interface)

    @app.post('/api/live/stop',dependencies=[Depends(control_monitor)],tags=['Live'])
    def live_stop(request:Request): return request.app.state.monitor.stop()

    @app.get('/docs',response_class=HTMLResponse,include_in_schema=False)
    def offline_docs():
        schema=app.openapi()
        rows=''.join(f'<tr><td>{html.escape(method.upper())}</td><td>{html.escape(path)}</td><td>{html.escape(operation.get("summary",""))}</td></tr>' for path,methods in schema['paths'].items() for method,operation in methods.items())
        return f'''<!doctype html><html lang="tr"><meta charset="utf-8"><title>Yerel API referansı</title><style>body{{font:16px system-ui;background:#101725;color:#e9f1fa;max-width:960px;margin:60px auto;padding:20px}}td{{padding:14px;border-bottom:1px solid #334155}}a{{color:#67ddeb}}code{{white-space:pre-wrap}}</style><h1>Fuzzy Network Risk API</h1><p>Tamamen yerel FastAPI / OpenAPI referansı. CDN gerektirmez.</p><a href="/openapi.json">OpenAPI şemasını aç / indir</a><table><tr><th>Yöntem</th><th>Adres</th><th>İşlem</th></tr>{rows}</table><h2>Analiz isteği</h2><code>{{"features": {{" Flow Packets/s": 100000, " Total Fwd Packets": 100, " Packet Length Mean": 6, " Bwd Packet Length Std": 0, " Down/Up Ratio": 0}}, "policy": "Balanced"}}</code><p>Geçersiz girdide 422 ve null puan döner. Veri kümesi etiketi kabul edilmez. Puan saldırı olasılığı değildir.</p><a href="/">Uygulamaya dön</a></html>'''

    dist=root/'web/dist'
    @app.get('/favicon.svg',include_in_schema=False)
    def favicon(): return FileResponse(dist/'favicon.svg',media_type='image/svg+xml')
    if (dist/'assets').exists(): app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/',include_in_schema=False)
    def frontend():
        if (dist/'index.html').exists(): return FileResponse(dist/'index.html')
        return HTMLResponse('<h1>Önyüz henüz derlenmedi</h1><p>web klasöründe npm ci ve npm run build çalıştırın.</p>',status_code=503)
    return app

app=create_app()
