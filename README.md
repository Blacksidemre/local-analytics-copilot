# Local Analytics Copilot

[![CI](https://github.com/Blacksidemre/local-analytics-copilot/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Blacksidemre/local-analytics-copilot/actions/workflows/ci.yml)

**Şirket verisini dışarı çıkarmadan çalışan, hesapları deterministik araçlarla yapan ve her sayısal
bulguyu kanıta bağlayan yerel AI veri analisti.**

> **Yayın durumu: pre-release — fiziksel Windows kabulü bekleniyor.** `main`, canonical tek-repo
> ürününü içerir; fakat gerçek Windows Tauri/installer ve canlı yerel Ollama Agent kabulü tamamlanana
> kadar stable `v1.0.0` yayımlanmayacaktır.

## Ürün deneyimi

```text
tek repo → tek uygulama → CSV/XLSX yükle → doğal dilde sor
         → deterministik analiz → bağımsız doğrulama → dashboard/rapor
```

LLM hesaplama motoru değildir:

```text
LLM planlar ve açıklar
        ↓
typed/bounded araçlar hesaplar
        ↓
verifier kanıtı doğrular
        ↓
UI yalnız doğrulanmış sonucu sunar
```

## Üç analiz modu

| Mod         | Ne yapar?                                                                                                    |                                                LLM gerekli mi? |
| ----------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------: |
| **Quick**   | Dosya profili, missing, duplicate copy, kolon rolleri ve güvenli KPI kartları                                |                                         Hayır; yorum opsiyonel |
| **Analyst** | Hedef seçimi, deterministik istatistik, multiple-testing, effect size, verifier ve rapor                     |                                      Hayır; açıklama opsiyonel |
| **Agent**   | Yerel Ollama planner ile bounded plan kurar, allowlist typed araçları zincirler ve verified synthesis üretir | Planlama için evet; model yoksa güvenli deterministik fallback |

Quick ve Analyst, Ollama çalışmasa da sayısal analiz üretebilir. Model çıktısı verifier'dan geçmezse
güvenilir sonuç gibi gösterilmez.

## Mevcut özellikler

### Dosya alımı ve veri kalitesi

- CSV encoding, delimiter, decimal, quote ve malformed-row kontrolü
- XLSX/XLSM sheet discovery, sheet selection ve header detection
- ZIP/XML tabanlı Excel arşiv güvenlik sınırları
- CSV/XLSX aynı typed ingestion ve finding sözleşmesi
- Satır/sütun, missing, exact duplicate copy, unique count, tarih aralığı ve schema profili
- Kaynak dosyayı değiştirmeyen çalışma alanı

### Deterministik analitik

- Numeric descriptive statistics ve categorical frequency
- Group/segment aggregation ve filtered aggregation
- Target-aware association screening
- Uygun parametrik/non-parametrik testler, effect size ve multiple-testing adjustment
- Outlier screening, correlation/association ve time trend
- Genel iş analitiği ile NPL/risk analiz çekirdeği

### Bounded local Agent

```text
user request → local Ollama planner → typed plan → deterministic tools
             → evidence manifest → verifier → bounded synthesis
```

Agent en fazla altı adımlık plan kullanır; failure budget, duplicate-call guard, dependency kontrolü
ve loop detection uygular. Planner'a raw dataset dökümü yerine schema, bounded profile, metadata ve
aggregate evidence verilir.

Agent şunları yapamaz:

- arbitrary Python, shell, PowerShell veya SQL çalıştırmak
- keyfi filesystem erişimi veya başka dosyaları okumak
- internet/cloud exfiltration başlatmak
- raw-row dump üretmek
- sahte `finding_id` veya evidence kullanmak
- kanıtsız sayı, KPI anlamı, benchmark veya business semantics uydurmak
- association sonucunu causality/prediction olarak sunmak

Beklenmeyen durumda davranış **fail closed** olur.

### Verifier, evidence ve raporlar

- Her authoritative sayı stable `finding_id` ve deterministic source taşır.
- Quick, Analyst ve Agent açıklamaları supplied evidence dışına çıkamaz.
- Verifier başarısızsa model metni güvenilir sonuç olarak yayımlanmaz.
- Excel, self-contained HTML ve PDF raporları aynı verified finding manifestini kullanır.
- Agent raporlarının üç formatı aynı SHA-256 binding ve aynı sayısal değerleri taşır.
- Ham satırlar ve doğrulanmamış model prose'u verified Agent raporlarına girmez.
- Üretilen dosyalar yeniden açılıp yapı, evidence, link/script ve formül hataları açısından kontrol edilir.

### Yerel geçmiş

Verifier-passed Agent çalışmaları yerel SQLite history store'a kaydedilebilir; listelenebilir,
açılabilir ve silinebilir. Saklanan içerik dataset-local fingerprint, istek özeti, kullanılan araçlar
ve bounded verified findings ile sınırlıdır.

Raw rows, model promptları/tool argümanları, secrets ve doğrulanmamış model metni otomatik saklanmaz.
Geçmiş bulgu yeni analizde otomatik gerçek kabul edilmez.

İki doğrulanmış çalışma UI'dan seçilerek karşılaştırılabilir. Sistem yalnız aynı `finding_id`, unit,
deterministic source ve dimension sözleşmesine sahip değerler için mutlak/oransal fark hesaplar;
eklenen, kaldırılan ve karşılaştırılamayan bulguları ayrı gösterir. Dönem veya iş anlamı otomatik
varsayılmaz: kullanıcı hangi kaydın önceki, hangisinin yeni olduğunu seçer.

## Local-first / offline-first

- Varsayılan model motoru yerel Ollama'dır; ücretli cloud API zorunlu değildir.
- Servisler loopback (`127.0.0.1`) üzerinde çalışır.
- Remote Ollama, cloud model etiketi ve web erişimi varsayılan kapalıdır.
- API token etkinse tüm `/api/` rotaları korunur.
- Dataset işlemleri workspace sınırları içinde kalır.
- SQL katmanı read-only AST guard ve DuckDB dış-dosya engelleri kullanır.
- Excel formula/URL injection ve rapor path traversal girişimleri reddedilir.
- Model veya Ollama yoksa deterministik Quick/Analyst çalışmaya devam eder.

İlk bağımlılık/model indirmeleri internet gerektirir. Kurulum ve seçilen Ollama modeli hazır olduğunda
yerel dosya analizi normal koşullarda çevrimdışı çalışabilir. Ayrıntılar:
[`docs/PRIVACY_AND_SECURITY.md`](docs/PRIVACY_AND_SECURITY.md).

## Tek canonical repository

Canonical kaynak yalnızca bu repodur:

```text
local-analytics-copilot/
├── apps/desktop/          # Hermetic-derived Next.js + Tauri ürün kabuğu
├── src/lacopilot/         # ingestion, analytics, Agent, verifier, reports, history
├── scripts/               # tek launcher ve paketleme girişleri
├── tests/                 # Python/integration/adversarial regression
├── docs/                  # mimari, güvenlik ve release belgeleri
└── workspace/             # yerel veri/çıktı sınırı; kullanıcı içeriği Git'e girmez
```

Eski `Blacksidemre/hermetic` repo yalnız historical/reference kaynaktır. Çalıştırma, build veya
paket çözümleme sırasında ona ihtiyaç yoktur. Hermetic'ten türetilen kaynak ve lisanslar
`apps/desktop` altında korunur.

## Windows ve geliştirici kurulumu

Ön koşullar:

- Windows 11, Linux veya macOS
- Python 3.11–3.13 (önerilen: 3.12)
- Node.js 22 veya 24
- pnpm 10.18.1
- AI yorum/Agent için Ollama ve seçilmiş yerel model

Windows hızlı başlangıç:

```powershell
git clone https://github.com/Blacksidemre/local-analytics-copilot.git
cd local-analytics-copilot
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_windows.ps1
pnpm desktop:install
pnpm dev
```

`pnpm dev`, Python backend ve birleşik web UI süreçlerini tek komutla yönetir. Kurulumdan sonra
`Start_Local_Analytics_Copilot.cmd` çift tıklanabilir.

Native Tauri geliştirme için ek olarak Rust stable, Visual Studio Build Tools içindeki **Desktop
development with C++**, MSVC ve Windows SDK gerekir:

```powershell
pnpm desktop:dev
```

Eksik native prerequisite anlaşılır hata ile bildirilir. Hazır `Setup.exe` henüz yayımlanmamıştır;
native Windows kabulü tamamlanmadan installer production-ready sayılmaz.

Ayrıntılı Türkçe rehber:
[`docs/KURULUM_VE_KULLANIM_TR.md`](docs/KURULUM_VE_KULLANIM_TR.md).

## İlk analiz

1. CSV veya XLSX yükleyin ve gerekiyorsa sheet seçin.
2. Quick, Analyst veya Agent modunu seçin.
3. Analyst/Agent için gerekiyorsa hedef sütunu ve doğrulanmış semantiği açıkça belirtin.
4. Örnek soru: `Bölgelere göre tahsilatı karşılaştır ve sorunlu segmentleri kanıtlarıyla sırala.`
5. Verifier sonucunu kontrol edin ve verified Excel/HTML/PDF raporunu indirin.

Business KPI tanımı verilmediyse kolon adı yalnızca kolon adı olarak kalır; sistem şirket kuralı
uydurmaz.

## Test ve kalite kapıları

```powershell
python -m pytest -q
python -m ruff format --check .
python -m ruff check .
python -m build
pnpm desktop:install
pnpm desktop:type-check
pnpm desktop:lint
pnpm desktop:test
pnpm web:build
```

Tek komutluk release-candidate veri kabulü, kontrollü sentetik CSV/XLSX üzerinde Quick/Analyst
paritesini, model-yok fallback'ini ve aynı manifest SHA-256'ına bağlı Excel/HTML/PDF raporlarını
çalıştırır:

```powershell
.\scripts\run_release_acceptance.ps1
```

Gerçek yerel Ollama planner/synthesis kabulünü zorunlu kılmak için hedef Windows makinede
`.\scripts\run_release_acceptance.ps1 -LiveAgent` kullanılır. Bu komut native Tauri pencere ve
installer etkileşimini doğrulamaz; fiziksel masaüstü kabulü ayrıca yapılır.

GitHub Actions ayrıca Python 3.11/3.12, Windows Python smoke/privacy, desktop contract/build,
Windows Tauri `cargo check --locked` ve paketlenmiş backend executable health smoke çalıştırır.

## Doğrulanmış ve bekleyen durum

| Alan                                                | Durum        |
| --------------------------------------------------- | ------------ |
| Milestone 1 — deterministic Quick CSV/XLSX          | PASS         |
| Milestone 2 — Analyst + verifier + verified reports | PASS         |
| Milestone 3 — bounded local Agent                   | PARTIAL      |
| Tek repo / tek launcher kaynak yapısı               | PASS         |
| Linux/Windows GitHub Actions                        | PASS         |
| Fiziksel Windows Tauri + canlı Ollama Agent E2E     | BEKLİYOR     |
| Stable `v1.0.0` / production installer              | YAYIMLANMADI |

Mevcut pre-release eksikleri:

1. Kontrollü CSV ve XLSX ile gerçek yerel Ollama Agent kabulü.
2. Hedef Windows makinede `pnpm desktop:dev` fiziksel Tauri E2E.
3. Windows installer build, kurulum, upgrade ve uninstall kabulü.
4. İsteğe bağlı project-level notlar ve onaylı dönem metadata'sı gibi v1.0 sonrası history
   genişletmeleri.

Release kapıları: [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md).

## Mimari ve güvenlik belgeleri

- [`docs/HYBRID_ARCHITECTURE.md`](docs/HYBRID_ARCHITECTURE.md)
- [`docs/ADR-001-agent-core.md`](docs/ADR-001-agent-core.md)
- [`docs/PRIVACY_AND_SECURITY.md`](docs/PRIVACY_AND_SECURITY.md)
- [`SECURITY.md`](SECURITY.md)
- [`WORK_HANDOFF.md`](WORK_HANDOFF.md)

## Lisans ve attribution

- Local Analytics Copilot: [`LICENSE`](LICENSE) — MIT
- Hermetic-derived desktop/web source: [`apps/desktop/LICENSE`](apps/desktop/LICENSE) — MIT,
  original copyright korunmuştur
- Vendored json-render: [`apps/desktop/src/spec/LICENSE`](apps/desktop/src/spec/LICENSE) — Apache-2.0
- Toplu attribution: [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)

Bu proje analitik yardımcı yazılımdır; OS izolasyonu, read-only veritabanı hesabı, firewall, DLP,
KVKK/GDPR kontrolleri veya kurum içi onayın yerine geçmez.
