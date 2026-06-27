// Initialize Leaflet Map centered over the BAY States, Nigeria
const map = L.map('map', {
    zoomControl: true
}).setView([11.5, 13.0], 7);

// Add clean, open-source OpenStreetMap base tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19
}).addTo(map);

// App State
let allSchools = [];
let mapMarkers = [];
let selectedSchool = null;
const overrides = new Map(); // Store override values: ID -> 'High' (Inaccessible) or 'Low' (Accessible)

// DOM Elements
const kpiTotal = document.getElementById('kpi-total');
const kpiCompromised = document.getElementById('kpi-compromised');
const kpiRate = document.getElementById('kpi-rate');

const filterState = document.getElementById('filter-state');
const filterTime = document.getElementById('filter-time');
const sliderVal = document.getElementById('slider-val');

const verificationDefault = document.getElementById('verification-default');
const verificationDetail = document.getElementById('verification-detail');
const detailName = document.getElementById('detail-name');
const detailState = document.getElementById('detail-state');
const detailLevel = document.getElementById('detail-level');
const detailVulnerability = document.getElementById('detail-vulnerability');
const detailOverride = document.getElementById('detail-override');

const btnOverrideAccessible = document.getElementById('btn-override-accessible');
const btnOverrideInaccessible = document.getElementById('btn-override-inaccessible');
const btnOverrideReset = document.getElementById('btn-override-reset');

// Fetch and load processed school GeoJSON data
async function loadSchoolData() {
    const dataPath = '../data/processed/bay_schools.geojson';
    
    try {
        const response = await fetch(dataPath);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const data = await response.json();
        
        // Parse features into structured school objects
        allSchools = data.features.map(f => {
            const props = f.properties;
            return {
                id: props.id || props.global_id || Math.random().toString(),
                name: props['School Name'] || props.name || 'Unnamed School',
                state: props.state_name || props.state_clean || 'Unknown',
                level: props['School Level'] || props.subtype || 'Primary',
                type: props['School Type'] || props.category || 'Regular',
                latitude: f.geometry.coordinates[1],
                longitude: f.geometry.coordinates[0],
                // Default vulnerability based on spatial buffer intersection
                modelVulnerability: props.vulnerability || props.vulnerability_score || 'Low',
                // Mock conflict date window for demo filtering purposes
                conflictDaysAgo: Math.floor(Math.random() * 90) + 1
            };
        });

        // Hide loading indicator if it exists
        const loadingIndicator = document.getElementById('map-loading');
        if (loadingIndicator) {
            loadingIndicator.style.opacity = '0';
            setTimeout(() => {
                loadingIndicator.style.display = 'none';
            }, 500);
        }

        updateDashboard();
    } catch (error) {
        console.error("Failed to load school GeoJSON data:", error);
    }
}

// Render schools on map and calculate KPI metrics
function updateDashboard() {
    const selectedState = filterState ? filterState.value : 'ALL';
    const maxDays = filterTime ? parseInt(filterTime.value) : 90;
    
    // Clear active map markers
    mapMarkers.forEach(m => map.removeLayer(m));
    mapMarkers = [];

    // Filter schools by state
    const filteredSchools = allSchools.filter(school => {
        return selectedState === 'ALL' || school.state.toLowerCase().trim() === selectedState.toLowerCase().trim();
    });

    let totalCount = 0;
    let compromisedCount = 0;

    filteredSchools.forEach(school => {
        totalCount++;

        // Determine actual status based on field overrides
        let vuln = school.modelVulnerability;
        let isOverridden = false;
        if (overrides.has(school.id)) {
            vuln = overrides.get(school.id);
            isOverridden = true;
        }

        // Mock time-slider interaction: if conflict occurred longer ago than slider window, treat as low-risk
        const withinTimeWindow = school.conflictDaysAgo <= maxDays;
        const isRed = (vuln.toLowerCase() === 'high' && withinTimeWindow);

        if (isRed) {
            compromisedCount++;
        }

        // Color scheme: Red (#E15759) for High risk, Green (#59A14F) for Low risk
        const markerColor = isRed ? '#E15759' : '#59A14F';
        const markerRadius = isRed ? 7 : 5;
        const fillOpacity = isRed ? 0.9 : 0.7;

        // Render as circle marker
        const marker = L.circleMarker([school.latitude, school.longitude], {
            radius: markerRadius,
            fillColor: markerColor,
            color: isOverridden ? '#f59e0b' : '#ffffff', // Amber border for overrides
            weight: isOverridden ? 2 : 1,
            opacity: 1,
            fillOpacity: fillOpacity
        });

        // Click handler to display school details in verification panel
        marker.on('click', () => {
            selectSchool(school);
        });

        // Custom warning text for high-risk spots
        let warningHtml = '';
        if (isRed) {
            warningHtml = `
                <div style="color: #E15759; font-weight: bold; margin-top: 6px; border-top: 1px solid #fee2e2; padding-top: 6px; font-size: 11px;">
                    ⚠️ High-Risk Spot: Location falls inside active conflict corridors. Proceed with caution.
                </div>`;
        }

        // Popup content displaying school information
        const popupContent = `
            <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
                <strong style="font-size: 13px; display: block; margin-bottom: 4px;">Facility: ${school.name}</strong>
                <strong>LGA:</strong> ${school.level}<br>
                <strong>State:</strong> ${school.state}<br>
                <strong>Status:</strong> <span style="color: ${isRed ? '#E15759' : '#59A14F'}; font-weight: bold;">${isRed ? 'Inaccessible' : 'Accessible'}</span>
                ${warningHtml}
                ${isOverridden ? `<div style="color: #d97706; font-weight: bold; margin-top: 4px; font-size: 10px;">⚠️ Field Overridden</div>` : ''}
            </div>
        `;

        marker.bindPopup(popupContent);
        marker.addTo(map);
        mapMarkers.push(marker);
    });

    // Update KPI panels dynamically
    if (kpiTotal) kpiTotal.innerText = totalCount.toLocaleString();
    if (kpiCompromised) kpiCompromised.innerText = compromisedCount.toLocaleString();
    
    const rate = totalCount > 0 ? ((compromisedCount / totalCount) * 100).toFixed(1) : '0.0';
    if (kpiRate) kpiRate.innerText = `${rate}%`;

    // Refresh selected school details if one is selected
    if (selectedSchool) {
        const refreshedSchool = allSchools.find(s => s.id === selectedSchool.id);
        if (refreshedSchool) selectSchool(refreshedSchool);
    }
}

// Display school information in field verification panel
function selectSchool(school) {
    selectedSchool = school;
    
    if (verificationDefault) verificationDefault.classList.add('hidden');
    if (verificationDetail) verificationDetail.classList.remove('hidden');
    
    if (detailName) detailName.innerText = school.name;
    if (detailState) detailState.innerText = school.state;
    if (detailLevel) detailLevel.innerText = `${school.level} (${school.type})`;
    
    if (detailVulnerability) {
        const isHighModel = school.modelVulnerability.toLowerCase() === 'high';
        detailVulnerability.innerText = isHighModel ? 'High (Inaccessible)' : 'Low (Accessible)';
        detailVulnerability.className = `font-bold px-2 py-0.5 rounded text-xs inline-block mt-1 ${
            isHighModel ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
        }`;
    }

    if (detailOverride) {
        const currentOverride = overrides.get(school.id);
        if (currentOverride) {
            detailOverride.innerText = currentOverride === 'High' ? 'Forced Inaccessible' : 'Forced Accessible';
            detailOverride.className = `font-bold px-2 py-0.5 rounded text-xs inline-block mt-1 ${
                currentOverride === 'High' ? 'bg-rose-600 text-white' : 'bg-emerald-600 text-white'
            }`;
        } else {
            detailOverride.innerText = 'None';
            detailOverride.className = 'font-bold px-2 py-0.5 rounded text-xs inline-block mt-1 bg-slate-950 text-slate-500 border border-slate-800';
        }
    }
}

// Filter listeners
if (filterState) {
    filterState.addEventListener('change', (e) => {
        const stateValue = e.target.value;
        
        // Flight centers configuration for smooth pan/zoom transitions
        const stateCenters = {
            'ALL': { center: [11.5, 13.0], zoom: 7 },
            'Borno': { center: [11.8, 13.1], zoom: 8 },
            'Adamawa': { center: [9.3, 12.5], zoom: 8 },
            'Yobe': { center: [12.0, 11.5], zoom: 8 }
        };

        const config = stateCenters[stateValue] || stateCenters['ALL'];
        map.flyTo(config.center, config.zoom, { duration: 1.0 });
        
        updateDashboard();
    });
}

if (filterTime) {
    filterTime.addEventListener('input', (e) => {
        if (sliderVal) sliderVal.innerText = `${e.target.value} Days`;
        updateDashboard();
    });
}

// Interactive field override listeners
if (btnOverrideAccessible) {
    btnOverrideAccessible.addEventListener('click', () => {
        if (selectedSchool) {
            overrides.set(selectedSchool.id, 'Low');
            updateDashboard();
        }
    });
}

if (btnOverrideInaccessible) {
    btnOverrideInaccessible.addEventListener('click', () => {
        if (selectedSchool) {
            overrides.set(selectedSchool.id, 'High');
            updateDashboard();
        }
    });
}

if (btnOverrideReset) {
    btnOverrideReset.addEventListener('click', () => {
        if (selectedSchool) {
            overrides.delete(selectedSchool.id);
            updateDashboard();
        }
    });
}

// Initialize on DOM load
window.addEventListener('DOMContentLoaded', loadSchoolData);
