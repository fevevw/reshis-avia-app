import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Решись Авиа: Цены", page_icon="✈️", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("seasonal_forecast.csv")
    return df


df = load_data()

mock_routes = {
    'MOW-AER': {'base_price': 9347, 'price_sensitivity': 0.15},
    'MOW-KGD': {'base_price': 7900, 'price_sensitivity': 0.10},
    'MOW-LED': {'base_price': 5994, 'price_sensitivity': 0.30},
    'MOW-MRV': {'base_price': 8476, 'price_sensitivity': 0.08},
    'MOW-OVB': {'base_price': 12728, 'price_sensitivity': 0.04}
}

city_to_code = {
    "Москва": "MOW",
    "Сочи": "AER",
    "Калининград": "KGD",
    "Санкт-Петербург": "LED",
    "Минеральные Воды": "MRV",
    "Новосибирск": "OVB"
}

def calculate_demand(row, entered_price, base_price, price_sensitivity, base_demand_col):
    demand = row[base_demand_col] - price_sensitivity * (entered_price - base_price)
    return demand

st.sidebar.title("🔐 Вход в систему")
password = st.sidebar.text_input("Введите пароль", type="password")

if password != "resis_avia2026":
    st.sidebar.warning("Введите пароль: resis_avia2026")
    st.title("✈️ Система динамического ценообразования")
    st.info("Пожалуйста, авторизуйтесь в левом меню, чтобы получить доступ к прогнозам (пароль: resis_avia2026).")
else:
    st.sidebar.success("Доступ разрешен!")
    st.title("✈️ Дашборд менеджера авиакомпании 'Решись Авиа'")
    st.markdown("Введи параметры рейса, и я скажу, сколько билетов купят и уместятся ли они в самолет.")
    col1, col2 = st.columns(2)
    with col1:
        city_from = st.selectbox("Откуда:", list(city_to_code.keys()), index=0)
        city_to = st.selectbox("Куда:", list(city_to_code.keys()), index=1)
        route_code = f"{city_to_code[city_from]}-{city_to_code[city_to]}"

    with col2:
        available_dates = sorted(df['date'].unique())
        selected_date = st.selectbox("Дата вылета:", available_dates)
        route_data = df[(df['route'] == route_code) & (df['date'] == selected_date)]

        if not route_data.empty:
            default_price = int(route_data['0.5_price'].values[0])
            entered_price = st.number_input("Цена билета (в рублях):", min_value=1000, max_value=50000,
                                            value=default_price, step=100)
        else:
            entered_price = st.number_input("Цена билета (в рублях):", min_value=1000, max_value=50000, value=10000,
                                            step=100)

    st.divider()
    if route_code not in mock_routes:
        st.error(
            f"К сожалению, маршрута {city_from} -> {city_to} ({route_code}) нет в нашей базе (в файле только 5 маршрутов из Москвы).")
    elif route_data.empty:
        st.error(f"На дату {selected_date} рейсов по маршруту {route_code} нет.")
    else:
        row = route_data.iloc[0]
        base_price = mock_routes[route_code]['base_price']
        sens = mock_routes[route_code]['price_sensitivity']
        seats = int(row['seats'])
        желают = calculate_demand(row, entered_price, base_price, sens, '0.5_base_demand')
        купят = min(seats, max(0, желают))

        st.subheader("Результаты прогноза:")
        m1, m2, m3 = st.columns(3)
        m1.metric("Всего мест в самолёте", seats)
        m2.metric("Сколько желают купить", round(желают, 1))
        m3.metric("Сколько реально купят", round(купят, 1),
                  delta=f"{round(купят - желают, 1)} (не влезли)" if желают > seats else "Все влезут!")

        if желают > seats:
            st.warning(
                "⚠️ Внимание! Спрос превышает количество мест. Самолет будет заполнен полностью (билеты раскупят).")
        elif желают < 0:
            st.info("📉 При такой цене желающих нет (спрос отрицательный, округляем до 0).")
        st.divider()
        st.subheader("📊 Вероятностный прогноз спроса")
        st.markdown(
            "График показывает, как может измениться спрос при введенной цене в зависимости от пессимистичного или оптимистичного сценариев.")

        graph_data = []
        quantiles = ['0.1', '0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9']

        for q in quantiles:
            demand_q = calculate_demand(row, entered_price, base_price, sens, f'{q}_base_demand')
            graph_data.append({
                "Сценарий": f"Сценарий {q}",
                "Вероятность": float(q) * 100,
                "Спрос (желают)": max(0, demand_q),
                "Тип": "Прогноз"
            })
        graph_data.append({"Сценарий": "Вместимость", "Вероятность": 50, "Спрос (желают)": seats, "Тип": "Места"})

        df_graph = pd.DataFrame(graph_data)
        fig = px.line(df_graph[df_graph['Тип'] == 'Прогноз'],
                      x='Вероятность',
                      y='Спрос (желают)',
                      title=f"Распределение спроса при цене {entered_price} руб.",
                      markers=True,
                      labels={'Вероятность': 'Квантиль, %', 'Спрос (желают)': 'Число пассажиров'})
        fig.add_hline(y=seats, line_dash="dash", line_color="red", annotation_text="Вместимость самолета")

        st.plotly_chart(fig, use_container_width=True)

        st.info(
            "💡 **Как это работает?** Формула: `Спрос = База - Чувствительность * (Цена - Базовая цена)`. Если цена растет, спрос падает. Система учитывает сценарии от пессимистичного (0.1) до оптимистичного (0.9).")