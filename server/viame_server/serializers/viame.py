"""
VIAME Fish format deserializer
"""
import csv
import re

from girder.models.file import File


def _deduceType(value):
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        number = float(value)
        return number
    except ValueError:
        return value


def _parse_row(row):
    """
    parse a single CSV line into its composite track and detection parts
    """
    features = {}
    attributes = {}
    track_attributes = {}
    confidence_pairs = [
        [row[i], float(row[i + 1])]
        for i in range(9, len(row), 2)
        if not row[i].startswith("(")
    ]
    start = len(row) - 1 if len(row) % 2 == 0 else len(row) - 2

    for j in range(start, len(row)):
        if row[j].startswith("(kp)"):
            if "head" in row[j]:
                groups = re.match(r"\(kp\) head ([0-9]+) ([0-9]+)", row[j])
                if groups:
                    features["head"] = (groups[1], groups[2])
            elif "tail" in row[j]:
                groups = re.match(r"\(kp\) tail ([0-9]+) ([0-9]+)", row[j])
                if groups:
                    features["tail"] = (groups[1], groups[2])
        if row[j].startswith("(atr)"):
            groups = re.match(r"\(atr\) (.+) (.+)", row[j])
            attributes[groups[1]] = _deduceType(groups[2])
        if row[j].startswith("(trk-atr)"):
            groups = re.match(r"\(trk-atr\) (.+) (.+)", row[j])
            track_attributes[groups[1]] = _deduceType(groups[2])
    return features, attributes, track_attributes, confidence_pairs


def load_csv_as_detections(file):
    rows = (
        b"".join(list(File().download(file, headers=False)()))
        .decode("utf-8")
        .split("\n")
    )
    reader = csv.reader(row for row in rows if (not row.startswith("#") and row))
    detections = []
    for row in reader:
        features, track_attributes, attributes, confidence_pairs = _parse_row(row)
        detections.append(
            {
                "track": int(row[0]),
                "frame": int(row[2]),
                "bounds": [float(row[3]), float(row[5]), float(row[4]), float(row[6]),],
                "confidence": float(row[7]),
                "fishLength": float(row[8]),
                "confidencePairs": confidence_pairs,
                "features": features,
                "attributes": attributes,
                "trackAttributes": track_attributes if track_attributes else None,
            }
        )
    return detections


def load_csv_as_tracks(file):
    """
    Convert VIAME web CSV to json tracks.
    Expect detections to be in increasing order (either globally or by track).
    """
    rows = (
        b"".join(list(File().download(file, headers=False)()))
        .decode("utf-8")
        .split("\n")
    )
    reader = csv.reader(row for row in rows if (not row.startswith("#") and row))
    tracks = {}

    for row in reader:
        features, track_attributes, attributes, confidence_pairs = _parse_row(row)
        trackid = int(row[0])
        frame = int(row[2])
        bounds = [
            float(row[3]),
            float(row[5]),
            float(row[4]),
            float(row[6]),
        ]
        fishLength = float(row[8])

        if trackid not in tracks:
            # track is defined as follows...
            tracks[trackid] = {
                # First frame with a feature
                "begin": frame,
                # Last frame with a feature
                "end": frame,
                # Unique among tracks in the video
                "key": trackid,
                # Array<{{ frame: number, foo: bar, ...}}>
                "features": [],
                # Key is an attribute name, val is a float confidence value
                "confidencePairs": {},
                # Key is string, value is freeform
                "attributes": {},
            }
        track = tracks[trackid]
        track["begin"] = min(frame, track["begin"])
        features["frame"] = frame
        features["bounds"] = bounds
        if fishLength > 0:
            features["fishLength"] = fishLength

        if attributes:
            features["attributes"] = attributes
        track["features"].append(features)
        for (key, val) in track_attributes:
            track["attributes"][key] = val
        if frame > track["end"]:
            track["end"] = frame
            # final confidence pair should be taken as the
            # pair that applied to the whole track
            for (key, val) in confidence_pairs:
                track["confidencePairs"][key] = val

    return tracks