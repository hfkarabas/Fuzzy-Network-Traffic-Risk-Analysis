"""Turkish presentation catalog, separate from inference parameters."""
FEATURES=[
    {'key':'rate','column':' Flow Packets/s','title':'Paket yoğunluğu','unit':'paket/sn','symbol':'pps',
     'description':'Akış boyunca saniye başına düşen paket sayısı.',
     'hint':'Yüksek değer yoğun trafiği veya çok kısa bir akışı gösterebilir. Düşük değer seyrek iletişimdir; tek başına güvenli ya da saldırı anlamına gelmez.'},
    {'key':'volume','column':' Total Fwd Packets','title':'İleri yön paket sayısı','unit':'paket','symbol':'pkt',
     'description':'Akışın başlangıç yönünde gözlenen toplam paket sayısı.',
     'hint':'Yüksek hacim uzun bir aktarımda normal olabilir. Az sayıda paket kısa bir işlem veya tarama olabilir; sayı tek başına saldırıyı kanıtlamaz.'},
    {'key':'size','column':' Packet Length Mean','title':'Ortalama paket boyutu','unit':'bayt','symbol':'B',
     'description':'Akış içindeki paket uzunluklarının ortalaması.',
     'hint':'Küçük paketler kontrol veya istek trafiği, büyük paketler veri aktarımı olabilir. Her iki davranış da meşru trafikte görülür.'},
    {'key':'variation','column':' Bwd Packet Length Std','title':'Geri yön boyut değişkenliği','unit':'bayt','symbol':'σ B',
     'description':'Geri yöndeki paket boyutlarının standart sapması.',
     'hint':'Yüksek değer boyutların değiştiğini gösterir. Sıfır, aynı boyutları veya az sayıda/hiç geri paket olmamasını gösterebilir; tek başına saldırı kanıtı değildir.'},
    {'key':'balance','column':' Down/Up Ratio','title':'Yön dengesi','unit':'oran','symbol':'↓/↑',
     'description':'Veri kümesinin dışa aktardığı tam sayı geri/ileri paket oranı.',
     'hint':'0 ileri yön ağırlığını, 1 yaklaşık dengeyi, daha büyük değerler geri yön ağırlığını anlatır. Tam sayıya indirgeme bilgi kaybettirir; 0 yanıt yok demek değildir.'},
]
TERMS={'sparse':'Seyrek','moderate':'Orta','intensive':'Yoğun','few':'Az','many':'Çok','small':'Küçük',
       'medium':'Orta','large':'Büyük','uniform':'Tekdüze','variable':'Değişken','highly_variable':'Çok değişken',
       'forward':'İleri ağırlıklı','balanced':'Dengeli','backward':'Geri ağırlıklı'}
LEVELS={'Low':'Düşük','Medium':'Orta','High':'Yüksek','Critical':'Kritik'}
POLICIES={'Sensitive':{'title':'Hassas','description':'Daha çok alarm; daha fazla yanlış alarm olasılığı.'},
          'Balanced':{'title':'Dengeli','description':'Alarm sıklığı ve kaçırma arasında ara çalışma noktası.'},
          'Conservative':{'title':'Temkinli','description':'Daha az alarm; daha fazla saldırıyı kaçırma olasılığı.'}}

def lower_tr(text): return text.replace('I','ı').replace('İ','i').lower()

def condition_text(expression):
    if 'feature' in expression:
        feature=next(f for f in FEATURES if f['key']==expression['feature'])
        return f"{feature['title']} {lower_tr(TERMS[expression['term']])}"
    operator=' VE ' if 'all' in expression else ' VEYA '
    return operator.join(condition_text(child) for child in expression.get('all',expression.get('any',[])))
