"""
Param generation module (production path).

Provides endpoints for generating an AI music parameter plan (meta/instruments/configs)
as a standalone step, saving outputs to disk for later pipeline stages.

This module does not produce MIDI notes or patterns – it only plans high-level
musical parameters that other modules (e.g. MIDI generation, rendering) can
consume later.
"""
