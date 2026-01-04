# pakiet: inventory
#
# ten pakiet odpowiada za "spis sampli" (inventory) dostępnych lokalnie w `local_samples/`.
# udostępnia:
# - budowę inventory.json (skan katalogów + klasyfikacja instrumentów)
# - odczyt i cache inventory w runtime
# - endpointy api do podglądu instrumentów i list sampli

from .router import router  # re-export dla łatwego podpięcia w aplikacji
