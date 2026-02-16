/**
 * Shared Leaflet map initialization for NH CPR Challenge.
 */

const DISTRICT_COLORS = {
    1: '#2563eb',
    2: '#059669',
    3: '#d97706',
    4: '#dc2626',
    5: '#7c3aed',
};

const COUNCILORS = {
    1: 'Joseph Kenney',
    2: 'Karen Liot Hill',
    3: 'Janet Stevens',
    4: 'John Stephen',
    5: 'Dave Wheeler',
};

// NH center coordinates
const NH_CENTER = [42.8, -71.5];
const NH_ZOOM = 7;

function createMap(elementId) {
    const map = L.map(elementId, {
        scrollWheelZoom: true,
    }).setView(NH_CENTER, NH_ZOOM);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
        maxZoom: 18,
    }).addTo(map);

    return map;
}

function addDistrictLayer(map, onDistrictClick) {
    fetch('/api/ec-districts.geojson')
        .then(r => r.json())
        .then(geojson => {
            L.geoJSON(geojson, {
                style: function(feature) {
                    const d = feature.properties.district;
                    return {
                        fillColor: DISTRICT_COLORS[d] || '#999',
                        fillOpacity: 0.15,
                        color: DISTRICT_COLORS[d] || '#999',
                        weight: 2,
                        opacity: 0.8,
                    };
                },
                onEachFeature: function(feature, layer) {
                    const d = feature.properties.district;
                    layer.bindTooltip(
                        '<strong>District ' + d + '</strong><br>' + (COUNCILORS[d] || ''),
                        { sticky: true }
                    );
                    if (onDistrictClick) {
                        layer.on('click', function() {
                            onDistrictClick(d);
                        });
                    }
                }
            }).addTo(map);
        });
}

function addTrainingMarkers(map, districtFilter) {
    let url = '/api/trainings';
    if (districtFilter) url += '?district=' + districtFilter;

    fetch(url)
        .then(r => r.json())
        .then(trainings => {
            trainings.forEach(t => {
                if (!t.latitude || !t.longitude) return;

                const marker = L.circleMarker([t.latitude, t.longitude], {
                    radius: 8,
                    fillColor: DISTRICT_COLORS[t.district] || '#333',
                    fillOpacity: 0.9,
                    color: '#ffffff',
                    weight: 2,
                });

                const dateStr = new Date(t.date + 'T00:00:00').toLocaleDateString('en-US', {
                    weekday: 'short', month: 'short', day: 'numeric'
                });

                marker.bindPopup(
                    '<div style="min-width:180px">' +
                    '<strong>' + t.location_name + '</strong><br>' +
                    '<span style="color:#666">' + dateStr + '</span>' +
                    (t.start_time ? ' &middot; ' + t.start_time : '') + '<br>' +
                    (t.city ? t.city + '<br>' : '') +
                    '<span style="color:#666">' + t.spots_remaining + ' spots left</span><br>' +
                    '<a href="/rsvp/' + t.id + '" style="color:#1e3a5f;font-weight:bold;">RSVP &rarr;</a>' +
                    '</div>'
                );

                marker.addTo(map);
            });
        });
}

/**
 * Initialize the trainings page map (smaller, with list below).
 */
function initTrainingsMap(elementId, districtFilter) {
    const map = createMap(elementId);
    addDistrictLayer(map, function(d) {
        window.location.href = '/trainings?district=' + d;
    });
    addTrainingMarkers(map, districtFilter);
}

/**
 * Initialize the full-page district map.
 */
function initDistrictMap(elementId) {
    const map = createMap(elementId);
    addDistrictLayer(map, function(d) {
        window.location.href = '/trainings?district=' + d;
    });
    addTrainingMarkers(map, null);
}
