# Local Analytics Copilot Desktop

Bu dizin, canonical [`Blacksidemre/local-analytics-copilot`](https://github.com/Blacksidemre/local-analytics-copilot)
ürününün Hermetic'ten türetilen Next.js + Tauri kabuğudur.

## Sınır

- UI, artifacts, dashboard rendering ve Tauri lifecycle bu dizindedir.
- CSV/XLSX ingestion truth, sayısal analiz, Agent evidence, verifier, history ve raporlar
  `src/lacopilot` servisinden gelir.
- Bu dizin tek başına ayrı bir ürün/repo değildir ve `achalp/hermetic` veya
  `Blacksidemre/hermetic` checkout'una runtime dependency taşımaz.
- Geliştirme ve kullanım komutları repository root'undan çalıştırılır.

```powershell
pnpm desktop:install
pnpm dev
# Native Windows prerequisite'leri hazırsa:
pnpm desktop:dev
```

Ana ürün, kurulum, güvenlik ve pre-release durumu için root [`README.md`](../../README.md) dosyasına
bakın.

## Attribution

Hermetic-derived kaynak için original MIT lisansı [`LICENSE`](LICENSE) içinde korunur. Vendored
Apache-2.0 bileşenleri ve font attribution bilgileri [`THIRD-PARTY-NOTICES.md`](THIRD-PARTY-NOTICES.md)
ve repository root [`THIRD-PARTY-NOTICES.md`](../../THIRD-PARTY-NOTICES.md) içinde yer alır.

Taşınan upstream README snapshot'ı yalnız tarihsel referans olarak
[`docs/archive/HERMETIC_UPSTREAM_README.md`](../../docs/archive/HERMETIC_UPSTREAM_README.md) altında
saklanır; güncel ürün talimatı değildir.
