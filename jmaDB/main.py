import flet as ft
import requests
import sqlite3


# 天気コードとアイコンのマッピング
WEATHER_CODES = {
    "100": {"name": "晴れ", "icon": ft.icons.WB_SUNNY},
    "101": {"name": "晴れ 時々 くもり", "icon": ft.icons.CLOUD_QUEUE},
    "103": {"name": "晴れ 時々 雨", "icon": ft.icons.UMBRELLA},
    "200": {"name": "くもり", "icon": ft.icons.CLOUD},
    "300": {"name": "雨", "icon": ft.icons.UMBRELLA},
    "400": {"name": "雪", "icon": ft.icons.AC_UNIT},
} 

def get_weather_info(code):
    """天気コードから情報を取得"""
    return WEATHER_CODES.get(code, {"name": "不明", "icon": ft.icons.HELP})

def fetch_data(url):
    """指定したURLからデータを取得"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"データ取得エラー: {e}")
        return None

def create_weather_card(date, weather_code, max_temp, min_temp):
    """天気カードを作成"""
    weather_info = get_weather_info(weather_code)
    return ft.Card(
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Text(date, weight="bold", size=14, color="#333"),
                    ft.Icon(weather_info["icon"], size=30, color="#FF9800"),
                    ft.Text(weather_info["name"], size=14, color="#555"),
                    ft.Row(
                        [
                            ft.Text(f"{min_temp}°C", size=14, color="#1976D2", weight="bold"),
                            ft.Text(" / ", size=14, color="#757575"),
                            ft.Text(f"{max_temp}°C", size=14, color="#D32F2F", weight="bold"),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                spacing=8,
            ),
            padding=10,
            width=140,
            height=160,
            bgcolor="#FFFFFF",
            border_radius=10,
        ),
        elevation=2,
    )

def init_db():
    conn = sqlite3.connect("weather.db")
    c = conn.cursor()
    # 地域テーブル
    c.execute('''
    CREATE TABLE IF NOT EXISTS regions (
        region_code TEXT PRIMARY KEY,
        region_name TEXT
    )
    ''')
    # 天気テーブル
    c.execute('''
    CREATE TABLE IF NOT EXISTS forecasts (
        region_code TEXT,
        forecast_date TEXT,
        weather_code TEXT,
        min_temp REAL,
        max_temp REAL,
        PRIMARY KEY (region_code, forecast_date),
        FOREIGN KEY (region_code) REFERENCES regions(region_code)
    )
    ''')
    conn.commit()
    conn.close()
def store_region_data_in_db(region_data):
    if not region_data:
        return
    conn = sqlite3.connect("weather.db")
    c = conn.cursor()
    for office_code, office_info in region_data["offices"].items():
        region_code = office_code
        region_name = office_info.get("name", "不明")
        c.execute('''
            INSERT OR IGNORE INTO regions (region_code, region_name)
            VALUES (?, ?)
        ''', (region_code, region_name))
    conn.commit()
    conn.close()
def store_weather_data_in_db(region_code, weather_data):
    if not weather_data or len(weather_data) < 2:
        return
    conn = sqlite3.connect("weather.db")
    c = conn.cursor()
    forecasts = weather_data[1]["timeSeries"][0]
    dates = forecasts["timeDefines"]
    areas = forecasts["areas"]
    area = areas[0]
    temp_data = weather_data[1]["timeSeries"][1]
    temp_area = temp_data["areas"][0]
    for i in range(len(dates)):
        date = dates[i].split("T")[0]
        weather_code = area["weatherCodes"][i]
        min_temp = temp_area.get("tempsMin", [None])[i] if "tempsMin" in temp_area else None
        max_temp = temp_area.get("tempsMax", [None])[i] if "tempsMax" in temp_area else None
        c.execute('''
            INSERT OR REPLACE INTO forecasts (region_code, forecast_date, weather_code, min_temp, max_temp)
            VALUES (?, ?, ?, ?, ?)
        ''', (region_code, date, weather_code, min_temp, max_temp))
    conn.commit()
    conn.close()
def get_forecasts_from_db(region_code):
    conn = sqlite3.connect("weather.db")
    c = conn.cursor()
    c.execute('SELECT region_name FROM regions WHERE region_code = ?', (region_code,))
    row = c.fetchone()
    region_name = row[0] if row else "不明"
    c.execute('SELECT forecast_date, weather_code, min_temp, max_temp FROM forecasts WHERE region_code = ? ORDER BY forecast_date', (region_code,))
    forecasts = c.fetchall()
    conn.close()
    return region_name, forecasts

def main(page: ft.Page):
    page.title = "天気予報アプリ"
    page.padding = 10
    page.theme_mode = ft.ThemeMode.LIGHT 

    # 地域データの取得
    region_data = fetch_data("http://www.jma.go.jp/bosai/common/const/area.json")
    if not region_data:
        page.add(ft.Text("地域データの取得に失敗しました"))
        return

    # 天気データを表示
    def show_weather(region_code):
        weather_data = fetch_data(f"https://www.jma.go.jp/bosai/forecast/data/forecast/{region_code}.json")
        if not weather_data or len(weather_data) < 2:
            weather_grid.controls = [ft.Text("天気データの取得に失敗しました")]
            page.update()
            return

        forecasts = weather_data[1]["timeSeries"][0]
        dates = forecasts["timeDefines"]
        areas = forecasts["areas"]

        temp_data = weather_data[1]["timeSeries"][1]
        temp_area = temp_data["areas"][0]

        cards = []
        for i, date in enumerate(dates):
            max_temp = temp_area.get("tempsMax", [None])[i]
            min_temp = temp_area.get("tempsMin", [None])[i]
            cards.append(create_weather_card(date.split("T")[0], areas[0]["weatherCodes"][i], max_temp, min_temp))

        weather_grid.controls = cards
        page.update()

    # サイドバーの作成
    def create_sidebar():
        sidebar = ft.Column(spacing=10, scroll = ft.ScrollMode.AUTO)
        for region_code, region_info in region_data["centers"].items():
            region_tile = ft.ExpansionTile(
                title=ft.Text(region_info["name"], color="white"),
                controls=[
                    ft.ListTile(
                        title=ft.Text(
                            region_data["offices"].get(sub_region, {}).get("name", "不明"),
                            color="white",
                        ),
                        on_click=lambda e, code=sub_region: show_weather(code),
                    )
                    for sub_region in region_info["children"]
                ],
            )
            sidebar.controls.append(region_tile)
        return sidebar

    weather_grid = ft.GridView(expand=True, runs_count=3, spacing=10, run_spacing=10)

    # レイアウト構築
    sidebar_container = ft.Container(
        content=create_sidebar(),
        width=250,
        bgcolor="#455A64",
        padding=10,
        border_radius=10,
    )

    page.add(
        ft.Row(
            [
                sidebar_container,
                ft.VerticalDivider(width=1),
                weather_grid,
            ],
            expand=True,
        )
    )

ft.app(target=main)         





