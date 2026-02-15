#!/usr/bin/env python3
"""One-time script to simplify EC district GeoJSON for browser performance.

Reduces coordinate precision and removes excess points using Douglas-Peucker
algorithm. No external dependencies beyond stdlib.
"""

import json
import math
import sys


def point_line_distance(point, start, end):
    """Perpendicular distance from point to line segment start-end."""
    if start == end:
        return math.sqrt((point[0] - start[0])**2 + (point[1] - start[1])**2)

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    t = max(0, min(1, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)))
    proj_x = start[0] + t * dx
    proj_y = start[1] + t * dy
    return math.sqrt((point[0] - proj_x)**2 + (point[1] - proj_y)**2)


def douglas_peucker(coords, epsilon):
    """Simplify a polyline using the Douglas-Peucker algorithm."""
    if len(coords) <= 2:
        return coords

    max_dist = 0
    max_idx = 0
    for i in range(1, len(coords) - 1):
        dist = point_line_distance(coords[i], coords[0], coords[-1])
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon:
        left = douglas_peucker(coords[:max_idx + 1], epsilon)
        right = douglas_peucker(coords[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [coords[0], coords[-1]]


def round_coords(coords, precision=5):
    """Round coordinate values to reduce file size."""
    return [round(c, precision) for c in coords]


def simplify_ring(ring, epsilon):
    """Simplify a polygon ring."""
    simplified = douglas_peucker(ring, epsilon)
    # Ensure ring is closed
    if simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    # Polygon needs at least 4 points (3 + closing)
    if len(simplified) < 4:
        return ring
    return [round_coords(c) for c in simplified]


def simplify_geometry(geometry, epsilon):
    """Simplify a GeoJSON geometry."""
    if geometry['type'] == 'Polygon':
        new_coords = []
        for ring in geometry['coordinates']:
            new_coords.append(simplify_ring(ring, epsilon))
        return {'type': 'Polygon', 'coordinates': new_coords}
    elif geometry['type'] == 'MultiPolygon':
        new_polys = []
        for polygon in geometry['coordinates']:
            new_rings = []
            for ring in polygon:
                new_rings.append(simplify_ring(ring, epsilon))
            new_polys.append(new_rings)
        return {'type': 'MultiPolygon', 'coordinates': new_polys}
    return geometry


def main():
    input_path = '/Users/chrismaidment/Downloads/New_Hampshire_Executive_Council_District_Boundaries_-_2022.geojson'
    output_path = '/Users/chrismaidment/nh-cpr-challenge/static/data/ec-districts.geojson'

    # Epsilon in degrees - ~0.002 degrees ≈ 200m, good for state-level map
    epsilon = 0.002

    with open(input_path) as f:
        data = json.load(f)

    print(f"Input: {len(json.dumps(data))} chars, {len(data['features'])} features")

    new_features = []
    for feature in data['features']:
        district = feature['properties'].get('ExecCo2022', 0)
        new_feature = {
            'type': 'Feature',
            'properties': {
                'district': district,
            },
            'geometry': simplify_geometry(feature['geometry'], epsilon)
        }
        new_features.append(new_feature)

        old_chars = len(json.dumps(feature['geometry']))
        new_chars = len(json.dumps(new_feature['geometry']))
        print(f"  District {district}: {old_chars} -> {new_chars} chars ({100*new_chars/old_chars:.1f}%)")

    output = {
        'type': 'FeatureCollection',
        'features': new_features
    }

    output_str = json.dumps(output)
    print(f"\nOutput: {len(output_str)} chars ({len(output_str)/1024:.1f} KB)")

    with open(output_path, 'w') as f:
        json.dump(output, f)

    print(f"Saved to {output_path}")


if __name__ == '__main__':
    main()
