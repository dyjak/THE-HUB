
# pakiet: midi_generation
#
# ten krok pipeline bierze `meta` z param_generation i generuje dane midi w formacie json.
# dodatkowo zapisuje artefakty na dysku (json, opcjonalnie .mid oraz podgląd svg pianoroll).
# część logiki jest "best-effort": jeśli nie da się stworzyć jakiegoś artefaktu, sam plan midi nadal wraca.

