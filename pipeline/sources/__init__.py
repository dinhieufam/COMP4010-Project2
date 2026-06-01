from pipeline.sources.neurips import NeurIPSSource


def get_adapter(venue: str):
    if venue.lower() == "neurips":
        return NeurIPSSource()
    raise ValueError(f"Unsupported venue for this MVP: {venue}")

