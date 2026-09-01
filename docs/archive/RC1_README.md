# Historical Local Analytics Copilot RC1 README

> **Archived/deprecated documentation.** This snapshot describes the pre-consolidation RC1 product.
> Use the repository root [`README.md`](../../README.md) for the current canonical single-repository
> product. Commands and feature status below are retained only as project history.

# Local Analytics Copilot 1.0 RC1

**Yerel çalışan veri analisti + istatistik mentoru + BI/Excel + NPL copilot.**

Amaç: hassas dosyaları varsayılan olarak bilgisayarınızda tutarken doğal dille veri inceleme, istatistiksel analiz, iş analizi, SQL, NPL analitiği, Pivot/dashboard/rapor ve şirket içi bilgi bankası kullanımı sağlamak.

> LLM planlar ve açıklar. Sayısal hesapları, dosya işlemlerini ve SQL'i deterministik Python/SQL araçları yapar.

> **Hibrit geliştirme dalı:** `hermetic-hybrid-integration`, Hermetic'in UI/Tauri/artifact
> katmanını LAC'ın deterministik analitik çekirdeğine bağlayan kontrollü geliştirme hattıdır.
> `main` bu çalışma sırasında değiştirilmez. Mimari kararlar:
> [`docs/HYBRID_ARCHITECTURE.md`](docs/HYBRID_ARCHITECTURE.md).

Bu integration dalı artık iki repo gerektirmez: deterministik Python servisleri ve Hermetic'ten
türetilen web/Tauri arayüzü aynı canonical repo içindedir. Kaynak arayüz
[`apps/desktop`](apps/desktop) altında, üçüncü taraf lisansları ise
[`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md) içinde korunur.

Geliştirici için tek giriş noktaları:

```powershell
pnpm desktop:install  # yalnız ilk kurulumda
pnpm dev              # birleşik tarayıcı deneyimi
pnpm desktop:dev      # native Tauri geliştirme penceresi
```

`pnpm dev` ve `pnpm desktop:dev`, LAC backend'i ve arayüzü birlikte yönetir; sabit geliştirici yolu
kullanmaz ve kendisinin başlatmadığı süreçleri kapatmaz. Kurulu Windows paketi henüz yayınlanmış
değildir; native Tauri kabulü Visual C++ Build Tools bulunan gerçek Windows makinede tamamlanacaktır.

> **Yayın durumu:** Bu sürüm bir release candidate'tır. Linux/Python 3.12 üzerinde lint, paketleme,
> güvenlik ve deterministik analiz testleri doğrulanmıştır. Windows 11 + RTX 5070 Ti, gerçek Ollama
> modelleri, Excel COM, canlı veritabanları ve OpenClaw entegrasyonu hedef bilgisayarda ayrıca
> doğrulanmalıdır. Ayrıntı: `docs/PRE_RELEASE_AUDIT.md`.

## İlk kez kuracaklar

Teknik bilginiz azsa **[Türkçe Adım Adım Kurulum ve Kullanım Rehberi](docs/KURULUM_VE_KULLANIM_TR.md)**
ile başlayın. Kısa yol:

1. Python 3.12 ve Ollama'yı kurun.
2. Repoyu ZIP olarak indirin ve klasöre çıkarın.
3. İlk kurulum için `.\scripts\install_windows.ps1` çalıştırın; `qwen3.5:9b` sorusuna `E`,
   ağır model sorusuna ilk kurulumda `H` deyin.
4. Sonraki açılışlarda `Start_Local_Analytics_Copilot.cmd` dosyasına çift tıklayın. Launcher
   Ollama, Docker, backend ve birleşik arayüz durumunu kontrol eder; gereken yerel süreçleri
   başlatıp uygulamayı açar.

`python` Windows aliası çalışmıyorsa kurucu otomatik olarak `py -3.12`, `py -3.13` ve
`py -3.11` seçeneklerini dener.

## Zorunlu ücret var mı?
**Hayır.** Varsayılan kurulum Ollama + yerel açık modeller + Python kütüphaneleridir. Ücretli OpenAI/Anthropic API anahtarı gerekmez. İnternet araştırması opsiyoneldir ve varsayılan olarak kapalıdır.

## Önerilen donanım profili
Bu repo özellikle **RTX 5070 Ti 16 GB VRAM + 32 GB RAM** sınıfı bir Windows makine düşünülerek ayarlanmıştır.

- Fast/Main: `qwen3.5:9b`
- Deep review/reasoning: `gpt-oss:20b` (opsiyonel)
- Başlangıç context: `32768`

Gerçek hız ve tool-calling güvenilirliğini kendi bilgisayarınızda `lac benchmark-models` ile ölçün.

## Ana özellikler

### Yerel AI / Agent
- Native Ollama `/api/chat` tool calling
- Fast / Main / Deep model modları
- Çok turlu tool loop + tur/context/result limitleri
- Sohbet geçmişi yerel SQLite'ta
- Model bulunamazsa güvenli fallback
- OpenClaw entegrasyonu opsiyonel; çekirdek ona bağımlı değil

### Kişilik & Mentor
- Mentor / Senior Analyst / Executive / Technical profilleri
- Kendi kişiliğinizi UI/API/YAML ile düzenleme
- Öğrenme seviyesi yerel profili
- “neden bu yöntem?” yaklaşımı
- Düz anlatım -> sonuç -> iş anlamı -> isteğe bağlı teknik detay

### Data Quality / ETL
- Deterministik CSV encoding/delimiter/decimal/quote algılama
- XLSX/XLSM sheet discovery ve header detection
- CSV/XLSX/XLSM/Parquet inceleme; bozuk dosyada kullanıcı dostu ve görünür hata
- Eksik veri, duplicate, constant kolon, schema drift
- IQR + robust Z outlier flag
- Açık data-quality kuralları
- Kaynağı değiştirmeden cleaning plan
- Lokal sentetik test verisi üretimi (formal privacy garantisi değildir)
- DuckDB ile dataset üzerinde read-only SQL

### İstatistik / Data Science
- Descriptive statistics + CI
- Welch t / Mann-Whitney
- Paired t / Wilcoxon
- One-way ANOVA / Welch ANOVA / Kruskal-Wallis + uygun olduğunda Tukey
- Chi-square / Fisher + Cramer's V
- Pearson / Spearman / Kendall
- Bootstrap CI
- Linear regression + VIF/Breusch-Pagan
- Logistic regression + Odds Ratio
- PCA
- K-Means + silhouette
- Isolation Forest
- Dataset drift
- Holt-Winters forecast + holdout backtest
- Kaplan-Meier survival
- Cross-validated Random Forest baseline + permutation importance
- Monte Carlo NPV

### Genel İş Analitiği
- Pareto / ABC
- Contribution / variance contribution
- Funnel
- Generic cohort
- RFM
- Break-even / target-profit

### BI / Excel / Dashboard
- Pivot/aggregation Excel çıktısı
- Executive Excel dashboard
- Offline self-contained Plotly HTML dashboard
- PDF summary formatter
- Deterministik dataset review workflow

### NPL / Varlık Yönetimi
- Portfolio summary
- DPD aging
- Debtor concentration / HHI
- Vintage curves
- Roll-rate / migration matrix
- Actual vs Target
- NPV / MOIC single & multi-scenario
- Monte Carlo valuation

### SQL / ERP
- PostgreSQL / SQL Server bağlantı profili altyapısı
- Schema catalog / table description
- Read-only query guard
- Query row caps + local audit
- Gerçek güvenlik için read-only DB hesabı zorunlu öneri

### Local RAG / Oryantasyon
- PDF/DOCX/TXT/MD/CSV/XLSX bilgi bankası
- SQLite FTS5
- Opsiyonel Ollama embeddings ile hybrid search
- Kaynak path + chunk bilgisini modele verir
- Şirket KPI/iş kurallarını uydurmama guardrail'i

### Kontrollü öğrenme / hafıza
- Agent yalnızca **candidate** rule/memory önerebilir
- Onayı yalnızca insan UI/API/CLI ile verir
- Tekrarlanan tool akışlarından reusable workflow adayı çıkarır
- Learning profile açıklama derinliğini adapte etmek için kullanılır

### Güvenlik
- Workspace sandbox
- Web varsayılan kapalı
- Uzak Ollama ve `:cloud` model etiketleri varsayılan kapalı
- PII-benzeri web sorgusu blokları
- AST tabanlı read-only SQL ve DuckDB dış dosya erişim engeli
- Workspace yazımı ve dış ağ çağrıları için gerçek insan onay kuyruğu
- Excel formula/URL injection koruması ve çıktıların üzerine yazmama
- Opsiyonel API token
- Audit JSONL
- Token olmadan ağ arayüzüne bind etmeyi reddetme

---

# Windows Kurulum

## 1. Ön koşullar
- Windows 11
- Python 3.11+
- Ollama
- NVIDIA sürücüsü

SQL Server kullanacaksanız ayrıca uygun Microsoft ODBC Driver gerekir.

## 2. PowerShell

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
```

Kurulum size modelleri indirmek isteyip istemediğinizi sorar.

Manuel kurulum:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[all,dev]"
copy .env.example .env
ollama pull qwen3.5:9b
# optional:
ollama pull gpt-oss:20b
```

## 3. Kontrol

```powershell
lac doctor
lac privacy-check
lac benchmark-models
```

## 4. Başlat

```powershell
.\Start_Local_Analytics_Copilot.cmd
```

Birleşik arayüz: `http://127.0.0.1:3000`

Data Bridge API: `http://127.0.0.1:8765`

Ayarlar:

`http://127.0.0.1:8765/admin`

---

# İlk Kullanım

Dosyalar:

```text
workspace/
├── incoming/     # analiz edilecek dosyalar
├── knowledge/    # prosedür, veri sözlüğü, KPI dokümanları
├── outputs/      # üretilen Excel/HTML/PDF
├── working/
├── archive/
└── logs/
```

Örnek demo verisi:

```powershell
python scripts/generate_demo_data.py
lac review incoming/demo_npl.csv --dashboard
```

Data Bridge regression verisini üretmek için:

```powershell
python scripts/generate_credit_risk_regression.py
```

Beklenen profil: `1508` satır, `22` sütun, `52` eksik hücre ve `8` exact duplicate kopya.

AI'ya örnek:

> `incoming/demo_npl.csv dosyasını bana giriş seviyesinde öğret. Önce veri kalitesi kontrolü yap, sonra DPD ve portföy performansını analiz et; uygun istatistikleri neden seçtiğini açıkla ve Excel dashboard oluştur.`

## Bilgi bankası

Dosyayı `workspace/knowledge` içine koyun:

```powershell
lac knowledge-ingest knowledge/veri_sozlugu.pdf
lac knowledge-search "Recovery Rate tanımı"
```

Embedding isterseniz lokal embedding modelini ayrıca kullanabilirsiniz; FTS arama embedding olmadan da çalışır.

Görüntü tabanlı/taranmış PDF için opsiyonel yerel OCR desteği vardır. Tesseract kurduktan sonra `pip install -e ".[ocr]"` ve `lac knowledge-ingest knowledge/taranmis.pdf --ocr` kullanabilirsiniz.

## Hafıza onayı

Agent bir şirket kuralını otomatik “doğru” kabul etmez:

```powershell
lac memory-list candidate
lac memory-approve 3
```

## Dosya / dış ağ işlemi onayı

Ajan Excel, HTML, PDF veya sentetik veri üretmek ya da internete sorgu göndermek istediğinde işlem
çalıştırılmaz; tam araç adı ve argümanlarıyla kuyruğa alınır. `/admin` ekranından inceleyebilir veya:

```powershell
lac action-list pending
lac action-approve ACTION_ID
# veya
lac action-reject ACTION_ID
```

Onay, yalnızca kuyruktaki değişmez araç + argüman çiftini çalıştırır.

## Öğrenme profili

```powershell
lac learning-profile
lac learning-update "Hypothesis Testing" 10 "Temel farkı anladım"
```

## File Watcher

```powershell
lac watch
```

`workspace/incoming` klasörüne yeni bir veri dosyası geldiğinde deterministik ilk inceleme JSON'u üretir.

---

# Database

Şifreleri YAML'a veya prompt'a koymayın. `.env` / environment variable kullanın.

```text
LAC_DB_MAIN_URL=postgresql+psycopg://...
LAC_DB_SQLSERVER_URL=mssql+pyodbc://...
```

`config/database_profiles.yaml` hangi env değişkeninin kullanılacağını söyler.

Production'da AI için ayrı **read-only** kullanıcı açın.

---

# İnternet modu

Varsayılan:

```text
LAC_ALLOW_WEB=false
```

Opsiyonel hybrid research:

```text
LAC_ALLOW_WEB=true
```

Web aracı ayrıca insan onayı ister. Bu ayar açıldığında yalnızca **public web araştırması** için
kullanın. Müşteri/borçlu satırlarını, iç raporları, gizli şirket bilgisini web sorgusuna koymayın.

---

# OpenClaw

OpenClaw opsiyonel ve bu RC'de **deneysel** bir entegrasyondur. Yerel Analytics Copilot, OpenClaw
olmadan da deterministik analiz motoru olarak çalışır. OpenClaw sürümü değiştikçe sağlayıcı davranışı
değişebileceğinden hedef makinede smoke-test edilmeden production orkestrasyonunda kullanmayın.

Bkz:
- `docs/OPENCLAW_INTEGRATION.md`
- `openclaw/SKILL.md`
- `openclaw/ollama-provider.example.json5`

---

# Geliştirme / Test

```powershell
ruff format --check .
ruff check .
pytest --cov=lacopilot --cov-report=term-missing -q
lac acceptance
lac project-review --mode deep
```

`hermetic-hybrid-integration` kapısı: **49 test, %66,29 kaynak kapsamı, sıfır Ruff ihlali**.
Donanım/model acceptance testleri Ollama çalıştığı hedef makinede ayrıca yürütülür.

`project-review` mimari/risk dokümanlarını **yerel deep model** ile eleştirel olarak inceler; cloud API kullanmaz.

---

# Önemli sınırlar

Bu yazılım:
- şirket politikasının yerine geçmez,
- istatistiksel sonucu otomatik iş kararı yapmaz,
- anomaly flag'ini fraud kanıtı saymaz,
- correlation/regression sonucunu otomatik nedensellik saymaz,
- sentetik veriye formal privacy garantisi vermez,
- şirket Recovery/KPI formüllerini siz onaylamadan “standart” kabul etmez.

Önce demo/sahte veriyle test edin; gerçek şirket verisinde bilgi güvenliği ve KVKK politikalarına uyun.

## Ayrıntılı dokümanlar
- `docs/ARCHITECTURE.md`
- `docs/ANALYTICS_CAPABILITIES.md`
- `docs/MASTER_PLAN.md`
- `docs/RISK_REGISTER.md`
- `docs/PRIVACY_AND_SECURITY.md`
- `docs/COSTS_AND_MODELS.md`
- `docs/REMOTE_ACCESS.md`
- `docs/OPENCLAW_INTEGRATION.md`
- `docs/GLOSSARY.md`
- `docs/PRE_RELEASE_AUDIT.md`
- `SECURITY.md`
- `CONTRIBUTING.md`
