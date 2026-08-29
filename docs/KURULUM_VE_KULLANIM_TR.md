# Local Analytics Copilot — Basit Kurulum ve Kullanım Rehberi

Bu rehber Windows'ta ilk kez kurulum yapan biri için hazırlanmıştır. Komutları sırayla uygulamanız
yeterlidir. İlk denemeyi gerçek şirket verisi yerine repodaki sentetik demo verisiyle yapın.

## En kısa cevaplar

| Soru | Kısa cevap |
|---|---|
| Ücretli mi? | Yerel kullanım için zorunlu abonelik veya ücretli API anahtarı yoktur. |
| OpenAI API anahtarı gerekiyor mu? | Hayır. |
| Ollama gerekiyor mu? | AI ile sohbet ve araç seçimi için evet; yalnızca deterministik CLI analizleri için hayır. |
| Ollama nedir? | AI modelini kendi bilgisayarınızda çalıştıran yerel model motorudur. |
| İlk hangi modeli kurmalıyım? | `qwen3.5:9b`. İlk kurulumda yalnızca bunu kurun. |
| Model ne kadar yer kaplar? | `qwen3.5:9b` indirmesi yaklaşık 6,6 GB'dır. |
| `gpt-oss:20b` şart mı? | Hayır. Opsiyonel, daha ağır ve yaklaşık 14 GB'dır. |
| Excel şart mı? | Hayır. `.xlsx` raporları Excel olmadan üretilebilir; native PivotTable için masaüstü Excel gerekir. |
| OpenClaw şart mı? | Hayır. Deneysel ve opsiyoneldir. İlk kurulumda kullanmayın. |
| İnternet sürekli gerekli mi? | İlk indirmeler için gerekir. Yerel model ve yerel dosyalarla normal kullanım çevrimdışı olabilir. |
| Veriler internete gider mi? | Varsayılan yerel ayarlarda web, uzak Ollama ve cloud model kullanımı kapalıdır. |
| GPU şart mı? | Hayır; CPU ile çalışabilir ama belirgin şekilde yavaş olur. NVIDIA GPU önerilir. |
| Bu sürüm production hazır mı? | Hayır. `1.0.0rc1` bir sürüm adayıdır; önce demo ve kendi cihaz testleri yapılmalıdır. |

## Sistem nasıl çalışıyor?

```text
Siz → Tarayıcı arayüzü → Local Analytics Copilot → Ollama → Yerel AI modeli
                              ↓
                    Python / SQL / Excel araçları
                              ↓
                   workspace/ içindeki yerel dosyalar
```

- **Ollama**, `qwen3.5:9b` gibi AI modelini çalıştırır.
- **Local Analytics Copilot**, soruyu anlar, uygun güvenli analiz aracını seçer, sonucu açıklar ve
  yazma/dış ağ işlemlerini insan onayına gönderir.
- **Python/SQL araçları**, sayısal hesapları yapar. Modelden hesap uydurması beklenmez.
- **OpenClaw**, ileride zamanlama veya daha geniş orkestrasyon için kullanılabilecek ayrı bir
  katmandır; çekirdek uygulamanın çalışması için gerekli değildir.

## Neler kurulacak?

| Bileşen | Neden gerekli? | Zorunlu mu? | Ücret |
|---|---|---:|---:|
| Python 3.11–3.13 | Analiz uygulamasını ve veri kütüphanelerini çalıştırır | Evet | Ücretsiz |
| Ollama | Yerel AI modelini çalıştırır | AI sohbeti için evet | Yerel kullanım ücretsiz |
| `qwen3.5:9b` | Ana yerel AI modeli | Önerilen | İndirme/kullanım ücreti yok |
| Python paketleri | Pandas, SciPy, FastAPI, Excel ve diğer özellikler | Evet | Ücretsiz |
| NVIDIA sürücüsü | GPU hızlandırması | NVIDIA GPU için | Ücretsiz |
| Git | Repoyu komutla indirmek ve güncellemek | Hayır | Ücretsiz |
| Microsoft Excel | Gerçek Excel COM/PivotTable otomasyonu | Hayır | Lisansınıza bağlı |
| SQL Server/PostgreSQL | Canlı veritabanı analizi | Hayır | Ortamınıza bağlı |
| OpenClaw | Opsiyonel orkestrasyon | Hayır | Seçtiğiniz kuruluma bağlı |

Ollama'nın cloud modelleri ve ücretli planları da vardır; bu proje onları varsayılan olarak
kullanmaz. Yerel kurulumun gerçek maliyeti yalnızca bilgisayarınızın disk alanı, elektrik tüketimi
ve internet indirmesidir.

## Önerilen bilgisayar

Hedef profil:

- Windows 11 64-bit
- RTX 5070 Ti 16 GB VRAM
- 32 GB veya daha fazla RAM
- En az 20 GB boş disk alanı; opsiyonel ağır modelle 35 GB veya daha fazlası daha rahattır
- Güncel NVIDIA ekran kartı sürücüsü

Daha düşük sistemlerde de çalışabilir. GPU yoksa cevaplar yavaşlar. Bellek sorunu yaşarsanız yalnızca
`qwen3.5:9b` kullanın, diğer GPU kullanan programları kapatın ve ağır modeli kurmayın.

---

# A. Sıfırdan Windows kurulumu

## 1. NVIDIA sürücüsünü kontrol edin

PowerShell açıp şunu yazın:

```powershell
nvidia-smi
```

Ekran kartı bilgisi görünüyorsa devam edin. Komut bulunamıyorsa veya hata veriyorsa NVIDIA'nın resmi
sürücü uygulamasından güncel sürücüyü kurup bilgisayarı yeniden başlatın.

## 2. Python 3.12 kurun

Python'ın resmi Windows kurulumunu indirin: <https://www.python.org/downloads/windows/>

Kurulum ekranında:

1. **Add Python to PATH** kutusunu işaretleyin.
2. Normal kurulumu tamamlayın.
3. Yeni bir PowerShell açın.
4. Kontrol edin:

```powershell
python --version
```

`Python 3.11`, `3.12` veya `3.13` görmelisiniz. En sorunsuz başlangıç önerisi Python 3.12'dir.
Python 3.14 bu RC1 tarafından henüz desteklenmez.

## 3. Ollama kurun

Resmi Windows sayfasından Ollama'yı kurun: <https://ollama.com/download/windows>

Normal Windows kurucusu en kolay seçenektir. Yerel model kullanmak için Ollama hesabı veya API anahtarı
gerekmez. Kurulumdan sonra Ollama'yı Başlat menüsünden bir kez açın ve yeni PowerShell'de kontrol edin:

```powershell
ollama --version
```

## 4. Projeyi indirin

En kolay yöntem:

1. GitHub repo sayfasında **Code** düğmesine basın.
2. **Download ZIP** seçin.
3. ZIP'i örneğin `C:\LocalAnalyticsCopilot` klasörüne çıkarın.
4. İç içe iki proje klasörü oluştuysa, `pyproject.toml` görünen klasöre girin.

Git kullanıyorsanız alternatif:

```powershell
git clone https://github.com/Blacksidemre/local-analytics-copilot.git
cd local-analytics-copilot
```

## 5. Doğru klasörde PowerShell açın

Dosya Gezgini'nde proje klasörünü açın. Adres çubuğuna `powershell` yazıp Enter'a basın. Aşağıdaki
dosyaları görmelisiniz:

```text
README.md
pyproject.toml
scripts/
src/
workspace/
```

Kontrol etmek için:

```powershell
Get-ChildItem
```

## 6. Uygulamayı kurun

Şu iki komutu çalıştırın:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
```

İlk komut yalnızca açık PowerShell penceresi için script çalıştırmaya izin verir; sistem genelindeki
kalıcı execution policy ayarını değiştirmez.

Kurulum script'i şunları yapar:

1. Python sürümünü kontrol eder.
2. Proje içinde `.venv` adlı izole Python ortamı kurar.
3. Gerekli Python paketlerini indirir.
4. `.env.example` dosyasından yerel `.env` ayarını oluşturur.
5. Otomatik testleri çalıştırır.
6. İsterseniz Ollama modelini indirir.

Sorular geldiğinde ilk kurulum için:

```text
qwen3.5:9b modelini şimdi indirmek ister misiniz? → E
gpt-oss:20b modelini de indirmek ister misiniz? → H
```

Model indirmesi yaklaşık 6,6 GB olduğu için bağlantınıza göre sürebilir. İndirme kesilirse aynı
komutu tekrar çalıştırabilir veya doğrudan şunu kullanabilirsiniz:

```powershell
ollama pull qwen3.5:9b
```

## 7. Kurulumu kontrol edin

Kurulum tamamlandıktan sonra aynı PowerShell'de:

```powershell
lac doctor
lac privacy-check
ollama list
```

Beklenen durum:

- `lac doctor`, workspace yolunu ve Ollama bağlantısını gösterir.
- `lac privacy-check`, web/remote/cloud seçeneklerinin kapalı olduğunu gösterir.
- `ollama list`, `qwen3.5:9b` modelini listeler.

İsterseniz kısa performans testi çalıştırın:

```powershell
lac benchmark-models
```

## 8. Önce güvenli demo testi yapın

```powershell
python scripts/generate_demo_data.py
lac review incoming/demo_npl.csv --dashboard
```

Bu komut gerçek kişi veya şirket verisi içermeyen sentetik bir NPL örnek dosyası oluşturur ve
deterministik ilk analizi çalıştırır. Çıktılar `workspace/outputs` klasörüne yazılır.

## 9. Tarayıcı arayüzünü başlatın

```powershell
.\scripts\start_windows.ps1
```

Ardından tarayıcıda açın:

- Ana ekran: <http://127.0.0.1:8765>
- Ayarlar ve onay kuyruğu: <http://127.0.0.1:8765/admin>

PowerShell penceresi açık kaldığı sürece uygulama çalışır. Durdurmak için PowerShell'de `Ctrl+C`
kullanın.

---

# B. Günlük kullanım

## 1. Her açılışta

1. Ollama'nın çalıştığından emin olun.
2. Proje klasöründe PowerShell açın.
3. Şunu çalıştırın:

```powershell
.\scripts\start_windows.ps1
```

4. <http://127.0.0.1:8765> adresini açın.

Kurulum script'ini her gün yeniden çalıştırmanız gerekmez.

## 2. Analiz edilecek dosyayı koyun

Dosyanızı şu klasöre kopyalayın:

```text
workspace/incoming/
```

Desteklenen temel biçimler: CSV, XLSX, XLSM, eski XLS ve Parquet.

Gerçek veri kullanmadan önce kurumunuzun KVKK, bilgi güvenliği ve veri işleme kurallarını kontrol edin.
Repo public olsa bile `workspace/incoming`, `workspace/knowledge`, çıktılar, loglar ve `.env` Git'e
gönderilmez.

## 3. Sohbette ne yazmalıyım?

İlk analiz için örnek:

> `incoming/portfoy.xlsx dosyasını önce veri kalitesi açısından incele. Kolonları ve sorunları basitçe
> anlat. Sonra yapılabilecek analizleri önem sırasına koy. Henüz dosyaya yazma; önce planı göster.`

NPL örneği:

> `incoming/demo_npl.csv için DPD dağılımını, tahsilat oranını, portföy karşılaştırmasını ve borçlu
> yoğunlaşmasını analiz et. Kullandığın yöntemleri başlangıç seviyesinde açıkla. Sonunda Excel dashboard
> oluşturmayı öner.`

İstatistik örneği:

> `A ve B portföylerinin tahsilat performansı gerçekten farklı mı? Varsayımları kontrol et, uygun testi
> kendin seç, effect size ve güven aralığını açıkla.`

Bilgi bankası örneği:

> `Şirket prosedüründeki Recovery Rate tanımını bul, kaynağını göster ve bu veri setindeki hesaplama ile
> uyumunu kontrol et.`

## 4. Neden bazı işlemler hemen yapılmıyor?

Dosya üretme/değiştirme veya dış internete çıkma gibi işlemler insan onayına alınır. Bu bir hata değil,
güvenlik özelliğidir. <http://127.0.0.1:8765/admin> sayfasında tam araç adını ve argümanları inceleyip
onaylayın veya reddedin.

CLI karşılığı:

```powershell
lac action-list pending
lac action-approve ACTION_ID
lac action-reject ACTION_ID
```

Tanımadığınız dosya yolu, URL veya argüman görürseniz işlemi onaylamayın.

## 5. Çıktıları nerede bulurum?

```text
workspace/outputs/
```

Bu klasörde Excel, HTML dashboard, PDF veya JSON çıktıları oluşabilir. Kaynak dosya varsayılan olarak
değiştirilmez ve mevcut çıktıların üzerine sessizce yazılmaz.

## 6. AI olmadan hızlı analiz

Ollama kapalı olsa bile deterministik profil ve review komutları kullanılabilir:

```powershell
lac analyze incoming/dosya.csv
lac review incoming/dosya.xlsx --dashboard
```

Bu komutlar model sohbeti yapmaz; doğrudan Python analiz motorunu çalıştırır.

## 7. Bilgi bankası

Prosedür, veri sözlüğü ve KPI dokümanlarını şuraya koyun:

```text
workspace/knowledge/
```

Sonra:

```powershell
lac knowledge-ingest knowledge/veri_sozlugu.pdf
lac knowledge-search "Recovery Rate tanımı"
```

FTS metin araması embedding modeli olmadan da çalışır. Taranmış/görüntü tabanlı PDF için ayrıca
Tesseract ve OCR bağımlılıkları gerekir; ilk kurulum için zorunlu değildir.

## 8. Şirket kuralı hafızası

Modelin önerdiği iş kuralları otomatik olarak doğru kabul edilmez:

```powershell
lac memory-list candidate
lac memory-approve 3
lac memory-reject 3
```

Yalnızca kurumunuzun resmi kaynağıyla doğruladığınız kuralları onaylayın.

---

# C. Ücret, gizlilik ve internet

## Yerel kullanım neden ücretsiz?

Uygulama Python paketlerini ve bilgisayarınıza indirilmiş bir modeli kullanır. Her mesaj için OpenAI,
Anthropic veya başka bir API'ye ödeme yapmaz. Projenin MIT lisansı vardır; önerilen `qwen3.5:9b`
modelinin Ollama sayfasında Apache 2.0 lisansı gösterilir.

Şunlar yine de maliyet oluşturabilir:

- Elektrik tüketimi
- Disk alanı
- İlk indirmelerde internet kotası
- Zaten sahip değilseniz Microsoft Excel lisansı
- İsteğe bağlı cloud model, üçüncü taraf API veya sunucu hizmetleri

## Veriler bilgisayardan çıkar mı?

Varsayılan `.env` ayarları:

```text
LAC_ALLOW_WEB=false
LAC_ALLOW_REMOTE_OLLAMA=false
LAC_ALLOW_CLOUD_MODELS=false
LAC_ALLOW_NETWORK_BIND=false
```

Bu ayarlarda uygulama yerel Ollama adresini ve yerel workspace'i kullanır. İlk kurulum sırasında Python
paketleri, repo ve model internetten indirilir; bu, analiz dosyanızın internete gönderildiği anlamına
gelmez. Web veya cloud özelliklerini sonradan açarsanız veri sınırını yeniden değerlendirin.

Ollama tarafında da local model adı kullanın; `:cloud` ile biten model etiketlerini bu proje varsayılan
olarak engeller. Tamamen local kalmak isteyen ileri kullanıcılar Ollama'nın resmi yönergesindeki
`OLLAMA_NO_CLOUD=1` ayarını ayrıca kullanabilir.

## Gerçek şirket verisi için minimum güvenlik listesi

1. Kurum ve bilgi güvenliği onayı alın.
2. Uygulamayı `127.0.0.1` üzerinde tutun; internete açmayın.
3. SQL bağlantısı için ayrı ve teknik olarak read-only kullanıcı kullanın.
4. `.env`, gerçek veri, bilgi bankası, log ve çıktıları GitHub'a yüklemeyin.
5. İlk analizleri veri kopyası ve salt-okunur akışta yapın.
6. `/admin` içindeki her write/external işlemini inceleyin.
7. Kritik finansal sonuçları insan analist ve resmi formülle doğrulayın.

---

# D. Sık karşılaşılan sorunlar

## `python` komutu bulunamadı

- Python'ı **Add Python to PATH** seçeneğiyle yeniden kurun.
- PowerShell'i kapatıp yeniden açın.
- `py -3.12 --version` komutunu deneyin.

## Script çalıştırma engellendi

Aynı PowerShell penceresinde:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Sonra script'i yeniden çalıştırın. `Scope Process` ayarı pencere kapanınca sona erer.

## `ollama` komutu bulunamadı

- Ollama'yı Başlat menüsünden açın.
- PowerShell'i yeniden başlatın.
- Gerekirse resmi Windows kurucusunu tekrar çalıştırın.

## `Ollama erişilemiyor` veya bağlantı reddedildi

Ollama uygulamasını açın. Gerekirse ayrı bir PowerShell'de:

```powershell
ollama serve
```

Ardından:

```powershell
lac doctor
```

## Model bulunamadı

```powershell
ollama pull qwen3.5:9b
ollama list
```

`.env` içinde `LAC_MODEL=qwen3.5:9b` olduğundan emin olun.

## GPU yerine CPU kullanılıyor veya çok yavaş

- `nvidia-smi` ile sürücüyü kontrol edin.
- Ollama ve bilgisayarı yeniden başlatın.
- GPU kullanan oyun/video/AI programlarını kapatın.
- İlk olarak yalnızca `qwen3.5:9b` kullanın.
- `gpt-oss:20b` modelini veya çok büyük context ayarını kullanmayın.

Gerçek hız donanım, model, context ve sürücüye bağlıdır; `lac benchmark-models` ile kendi sisteminizde
ölçün.

## Bellek yetersiz / model kapanıyor

`.env` içinde başlangıç için:

```text
LAC_FAST_MODEL=qwen3.5:9b
LAC_MODEL=qwen3.5:9b
LAC_CONTEXT_WINDOW=8192
```

ile deneyin. Sistem stabil olduğunda context'i kademeli artırabilirsiniz.

## `8765` portu kullanımda

```powershell
.\.venv\Scripts\Activate.ps1
lac serve --host 127.0.0.1 --port 8766
```

Sonra <http://127.0.0.1:8766> adresini açın.

## Excel kurulu değil

Normal `.xlsx` raporları yine üretilebilir. Yalnızca Windows Excel COM ile oluşturulan gerçek native
PivotTable özelliği kullanılamaz.

## SQL bağlantısı çalışmıyor

- SQL özelliği ilk kullanım için zorunlu değildir.
- SQL Server için Microsoft ODBC Driver gerekebilir.
- Uygulama ayarından bağımsız olarak veritabanında gerçekten read-only bir hesap kullanın.
- Önce sentetik veya test veritabanında deneyin.

## Tarayıcı açılmıyor

PowerShell'de uygulamanın çalışmaya devam ettiğini kontrol edin ve adresi elle yazın:

```text
http://127.0.0.1:8765
```

`https://` değil, yerel kullanımda `http://` kullanılır.

## Testlerden biri hata verdi

Hata metnini saklayın ve GitHub Issues üzerinden şu bilgileri ekleyin:

- Windows sürümü
- `python --version`
- `ollama --version`
- `nvidia-smi` çıktısındaki GPU/sürücü bilgisi
- Çalıştırdığınız komut
- Hatanın tamamı; fakat gerçek veri, parola, API token veya bağlantı URL'si olmadan

---

# E. Güncelleme ve kaldırma

## Git ile güncelleme

Önemli çıktılarınızı yedekledikten sonra proje klasöründe:

```powershell
git pull
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[all,dev]"
python -m pytest -q
```

ZIP ile kurduysanız yeni sürümü ayrı bir klasöre çıkarın; eski `.env`, gerçek veri ve çıktıları ne
taşıdığınızı kontrol etmeden topluca kopyalamayın.

## Bir modeli kaldırma

```powershell
ollama list
ollama rm qwen3.5:9b
```

## Uygulamayı kaldırma

1. Uygulamayı `Ctrl+C` ile kapatın.
2. Gerekli çıktı/verileri yedekleyin.
3. Proje klasörünü Windows Dosya Gezgini üzerinden silin.
4. Ollama'yı da istemiyorsanız Windows **Yüklü uygulamalar** ekranından kaldırın.

Ollama'yı kaldırmak ile model dosyalarını kaldırmak aynı işlem olmayabilir; önce `ollama rm MODEL_ADI`
kullanmak daha kontrollüdür.

---

# F. Son kontrol listesi

Gerçek kullanıma geçmeden önce hepsinin doğru olduğundan emin olun:

- [ ] `python --version` desteklenen sürümü gösteriyor.
- [ ] `ollama list` içinde `qwen3.5:9b` var.
- [ ] `lac doctor` Ollama'ya ulaşıyor.
- [ ] `lac privacy-check` web, remote ve cloud için güvenli durumu gösteriyor.
- [ ] 35 otomatik test kurulurken geçti.
- [ ] Sentetik demo analizi ve dashboard üretimi çalıştı.
- [ ] Tarayıcı arayüzü yalnızca `127.0.0.1` üzerinden açılıyor.
- [ ] Gerçek veri kullanımı için kurum/bilgi güvenliği onayı var.
- [ ] SQL hesabı gerekiyorsa gerçekten read-only.
- [ ] Onay kuyruğunu nasıl inceleyeceğinizi biliyorsunuz.

Bu liste geçildikten sonra gerçek cihaz bulgularını GitHub Issues'a kaydedip RC1'i birlikte
iyileştirebiliriz.

## Resmi kaynaklar

- Ollama Windows kurulumu: <https://docs.ollama.com/windows>
- Ollama indirme: <https://ollama.com/download/windows>
- Ollama hızlı başlangıç: <https://docs.ollama.com/quickstart>
- Ollama gizlilik/yerel çalışma SSS: <https://docs.ollama.com/faq>
- `qwen3.5:9b` model sayfası: <https://ollama.com/library/qwen3.5:9b>
- Python Windows indirmeleri: <https://www.python.org/downloads/windows/>
