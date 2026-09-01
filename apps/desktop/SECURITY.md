# Desktop security policy

Canonical güvenlik politikası repository root [`SECURITY.md`](../../SECURITY.md) dosyasındadır.

Hermetic-derived desktop kaynakları aynı fail-closed sınırların parçasıdır: loopback-only servisler,
bounded API proxy, minimum Tauri capability, child-process lifecycle, local API token ve untrusted
dataset/prompt-injection varsayımı.

Güvenlik açığını eski Hermetic upstream/forkuna değil, bu canonical repository'nin private
vulnerability reporting kanalına bildirin. Secret, kişisel veri veya unredacted log içeren public
issue açmayın.

Taşınan upstream güvenlik metni provenance için
[`docs/archive/HERMETIC_UPSTREAM_SECURITY.md`](../../docs/archive/HERMETIC_UPSTREAM_SECURITY.md)
altında korunur; güncel reporting adresi değildir.
