from flask import Flask, jsonify, request
from flask_cors import CORS
import math, requests, datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)
CORS(app)

def geocode_city(city_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {'q': city_name, 'format': 'json', 'limit': 1}
    headers = {'User-Agent': 'SoulCodesAstrology/1.0 contact@divinetimingcoaching.com'}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=8)
        data = r.json()
        if data:
            return float(data[0]['lat']), float(data[0]['lon']), data[0].get('display_name', city_name)
    except Exception:
        pass
    return None, None, None

def get_utc_offset(lat, lon, birth_date, birth_time):
    try:
        url = f"https://timeapi.io/api/timezone/coordinate?latitude={lat}&longitude={lon}"
        r = requests.get(url, timeout=6, headers={"User-Agent": "SoulCodes/1.0"})
        data = r.json()
        tz_name = data.get("timeZone")
        if tz_name:
            tz = ZoneInfo(tz_name)
            year, month, day = [int(x) for x in birth_date.split('-')]
            hour, minute = [int(x) for x in birth_time.split(':')]
            dt = datetime.datetime(year, month, day, hour, minute, tzinfo=tz)
            return dt.utcoffset().total_seconds() / 3600, tz_name
    except Exception:
        pass
    # Fallback: estimate from longitude
    return round(lon / 15), "estimated"

def julian_day(year, month, day, hour_ut):
    if month <= 2:
        year -= 1
        month += 12
    A = int(year / 100)
    B = 2 - A + int(A / 4)
    return (int(365.25 * (year + 4716))
            + int(30.6001 * (month + 1))
            + day + hour_ut / 24.0 + B - 1524.5)

def gmst(jd):
    T = (jd - 2451545.0) / 36525.0
    g = (280.46061837 + 360.98564736629 * (jd - 2451545.0)
         + 0.000387933 * T**2 - T**3 / 38710000.0)
    return g % 360

def local_sidereal_time(jd, lon):
    return (gmst(jd) + lon) % 360

def obliquity(jd):
    T = (jd - 2451545.0) / 36525.0
    return 23.439291111 - 0.013004167 * T - 0.0000001639 * T**2 + 0.0000005036 * T**3

def calc_asc(jd, lat, lon):
    eps = math.radians(obliquity(jd))
    lst = math.radians(local_sidereal_time(jd, lon))
    lat_r = math.radians(lat)
    asc = math.atan2(math.cos(lst),
        -(math.sin(lst) * math.cos(eps) + math.tan(lat_r) * math.sin(eps)))
    return math.degrees(asc) % 360

def calc_mc(jd, lon):
    eps = math.radians(obliquity(jd))
    lst = math.radians(local_sidereal_time(jd, lon))
    mc = math.atan2(math.sin(lst), math.cos(lst) * math.cos(eps))
    return math.degrees(mc) % 360

SIGNS = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo',
         'Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces']

def to_sign(deg):
    deg = deg % 360
    return SIGNS[int(deg / 30)], round(deg % 30, 2)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'Soul Codes API v2.0'})

@app.route('/calculate-rising', methods=['POST'])
def calculate_rising():
    data = request.json or {}
    for f in ['birth_date', 'birth_time', 'birth_city']:
        if f not in data:
            return jsonify({'error': f'Missing: {f}'}), 400
    try:
        lat, lon, display = geocode_city(data['birth_city'])
        if lat is None:
            return jsonify({'error': f'City not found: {data["birth_city"]}. Try adding the country e.g. "Arequipa, Peru"'}), 400

        if 'utc_offset' in data and data['utc_offset'] is not None:
            utc_offset = float(data['utc_offset'])
            tz_name = "manual"
        else:
            utc_offset, tz_name = get_utc_offset(lat, lon, data['birth_date'], data['birth_time'])

        year, month, day = [int(x) for x in data['birth_date'].split('-')]
        hour, minute = [int(x) for x in data['birth_time'].split(':')]
        hour_ut = (hour + minute / 60.0) - utc_offset
        if hour_ut < 0:    hour_ut += 24; day -= 1
        elif hour_ut >= 24: hour_ut -= 24; day += 1

        jd = julian_day(year, month, day, hour_ut)
        asc_deg = calc_asc(jd, lat, lon)
        mc_deg  = calc_mc(jd, lon)

        asc_sign, asc_d = to_sign(asc_deg)
        mc_sign,  mc_d  = to_sign(mc_deg)
        dsc_sign, dsc_d = to_sign((asc_deg + 180) % 360)
        ic_sign,  ic_d  = to_sign((mc_deg  + 180) % 360)

        return jsonify({
            'rising_sign': asc_sign, 'rising_degree': asc_d,
            'mc_sign': mc_sign, 'mc_degree': mc_d,
            'dsc_sign': dsc_sign, 'dsc_degree': dsc_d,
            'ic_sign': ic_sign, 'ic_degree': ic_d,
            'utc_offset': utc_offset, 'timezone': tz_name,
            'birth_lat': round(lat, 4), 'birth_lon': round(lon, 4),
            'city_resolved': display,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/geocode', methods=['POST'])
def geocode():
    data = request.json or {}
    city = data.get('city', '').strip()
    if not city:
        return jsonify({'error': 'No city provided'}), 400
    lat, lon, display = geocode_city(city)
    if lat is None:
        return jsonify({'error': 'City not found'}), 404
    return jsonify({'lat': lat, 'lon': lon, 'display_name': display})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
