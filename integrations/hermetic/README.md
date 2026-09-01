# Historical bridge adapter

Bu dizindeki TypeScript adapter contract, iki-repo döneminde LAC Data Bridge'in Hermetic UI'a nasıl
bağlanacağını belgelemek için oluşturuldu. Canonical entegrasyon artık doğrudan
[`apps/desktop`](../../apps/desktop) içinde yaşar.

- Ayrı `Blacksidemre/hermetic` checkout'u gerekmez.
- Bu dizin runtime/package dependency değildir.
- Yeni ürün geliştirmesi burada veya eski Hermetic forkunda yapılmamalıdır.
- Contract değişikliği gerekiyorsa canonical `apps/desktop/src/lib/lac-bridge-client.ts` ve Python
  API testleri birlikte güncellenmelidir.

Eski adapter açıklaması yalnız tarihsel referans olarak
[`docs/archive/HERMETIC_ADAPTER_README.md`](../../docs/archive/HERMETIC_ADAPTER_README.md) altında
saklanır.
