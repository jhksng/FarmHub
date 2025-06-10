# 제어 루프
def start_control_loop(crop_name, stop_event):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {crop_name} 제어 루프 시작됨.")

    # --- 생장등 타이머 로직 변경 ---
    # 상태(state)를 추가하여 'ON', 'COOLING_DOWN', 'PAUSED'를 관리
    light_timer = {
        'state': 'COOLING_DOWN',             # 초기 상태는 꺼진 상태(쿨다운)로 시작
        'start_time': None,                  # LED가 켜지기 시작한 시간
        'remaining_seconds': 0,              # 수동으로 껐을 때 남은 시간
        'cooldown_end_time': datetime.now()  # 쿨다운이 끝나는 시간, 시작 시 바로 켜지도록 초기화
    }
    # --------------------------------

    last_water_time = datetime.min
    last_soil_check_timestamp = None
    last_heat_time = datetime.min
    last_temp_check_timestamp = None
    water_cooldown_seconds = 600
    heater_cooldown_seconds = 600

    loop_count = 0

    while not stop_event.is_set():
        loop_count += 1
        print(f"\n--- {loop_count}번째 루프 ({crop_name}) ---")

        # (기존 작물 변경 감지 로직은 그대로 유지)
        db_conn = get_db_connection()
        cursor = db_conn.cursor()
        cursor.execute("SELECT selected_crop FROM users LIMIT 1")
        db_selected_crop_result = cursor.fetchone()
        cursor.close()
        db_conn.close()

        if db_selected_crop_result and db_selected_crop_result[0] != crop_name:
            new_crop_name = db_selected_crop_result[0]
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 작물 변경 감지: {crop_name} -> {new_crop_name}. 제어 루프 종료.")
            stop_event.set()
            continue

        crop_settings = load_crop_settings(crop_name)
        sensor = get_latest_sensor_values(crop_name)
        now = datetime.now()

        if not crop_settings or not sensor:
            print("설정이나 센서값 없음. 10초 대기")
            time.sleep(10)
            continue

        # --- ✨ 1. 생장등 24시간 주기 및 수동 제어 로직 ✨ ---
        
        # 상태: COOLING_DOWN (꺼져 있고, 쿨다운 시간이 끝나면 켤 차례)
        if light_timer['state'] == 'COOLING_DOWN':
            if now >= light_timer['cooldown_end_time']:
                print(f"[{now.strftime('%H:%M:%S')}] 생장등 쿨다운 종료. 새로운 조명 사이클 시작.")
                light_timer['state'] = 'ON'
                light_timer['start_time'] = now
                # DB에서 설정한 시간을 초 단위로 변환하여 목표 시간으로 설정
                light_timer['remaining_seconds'] = crop_settings['light_duration'] * 3600
                control_device('LED', 0) # LED 켜기
                print(f"[{now.strftime('%H:%M:%S')}] 생장등 켜짐 (목표: {crop_settings['light_duration']}시간)")

        # 상태: ON (켜져 있는 상태)
        elif light_timer['state'] == 'ON':
            # ✨ 수동 제어 감지: 'ON' 상태여야 하는데, 실제 핀이 꺼져있다면 사용자가 끈 것으로 간주
            if state[pins['LED']] == 1: # 1이 OFF
                print(f"[{now.strftime('%H:%M:%S')}] 생장등 수동 OFF 감지. 타이머를 일시정지합니다.")
                light_timer['state'] = 'PAUSED'
                # 지금까지 켜져 있던 시간을 계산
                elapsed_seconds = (now - light_timer['start_time']).total_seconds()
                # 남은 시간을 계산하여 저장
                light_timer['remaining_seconds'] -= elapsed_seconds
                if light_timer['remaining_seconds'] < 0:
                    light_timer['remaining_seconds'] = 0
                
                hours = int(light_timer['remaining_seconds'] // 3600)
                minutes = int((light_timer['remaining_seconds'] % 3600) // 60)
                print(f"남은 작동 시간: {hours}시간 {minutes}분")

            else: # 자동으로 계속 켜져 있는 경우
                elapsed_seconds = (now - light_timer['start_time']).total_seconds()
                if elapsed_seconds >= light_timer['remaining_seconds']:
                    print(f"[{now.strftime('%H:%M:%S')}] 생장등 목표 시간 완료. 쿨다운을 시작합니다.")
                    control_device('LED', 1) # LED 끄기
                    light_timer['state'] = 'COOLING_DOWN'
                    # 쿨다운 시간 계산 (24시간 - 켠 시간)
                    cooldown_duration = (24 - crop_settings['light_duration']) * 3600
                    light_timer['cooldown_end_time'] = now + timedelta(seconds=cooldown_duration)
                    print(f"다음 작동 시간: {light_timer['cooldown_end_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                else: # 계속 켜져있는 상태 정보 출력
                    remaining = light_timer['remaining_seconds'] - elapsed_seconds
                    hours = int(remaining // 3600)
                    minutes = int((remaining % 3600) // 60)
                    print(f"[{now.strftime('%H:%M:%S')}] 생장등 켜짐. 남은 시간: {hours}시간 {minutes}분")

        # 상태: PAUSED (수동으로 꺼서 멈춘 상태)
        elif light_timer['state'] == 'PAUSED':
            # ✨ 수동 제어 감지: 'PAUSED' 상태인데, 실제 핀이 켜졌다면 사용자가 다시 켠 것으로 간주
            if state[pins['LED']] == 0: # 0이 ON
                print(f"[{now.strftime('%H:%M:%S')}] 생장등 수동 ON 감지. 남은 시간부터 타이머를 재개합니다.")
                light_timer['state'] = 'ON'
                light_timer['start_time'] = now # 타이머 시작 시간을 현재로 재설정
                
                hours = int(light_timer['remaining_seconds'] // 3600)
                minutes = int((light_timer['remaining_seconds'] % 3600) // 60)
                print(f"재개된 작동 시간: {hours}시간 {minutes}분")


        # --- (기존 워터펌프, 히터, 쿨러 로직은 그대로 유지) ---

        # 워터펌프 조건
        if (sensor['soil'] < crop_settings['soil'] and
            (sensor['timestamp'] != last_soil_check_timestamp or last_soil_check_timestamp is None) and
            (now - last_water_time).total_seconds() >= water_cooldown_seconds):

            print(f"토양 수분 부족 ({sensor['soil']}% < 목표 {crop_settings['soil']}%) → 워터펌프 작동")
            threading.Thread(target=water_pump_routine).start()
            last_water_time = now
            last_soil_check_timestamp = sensor['timestamp']

        # 히터 조건
        if (sensor['temp'] < crop_settings['temp'] - 2 and
            (sensor['timestamp'] != last_temp_check_timestamp or last_temp_check_timestamp is None) and
            (now - last_heat_time).total_seconds() >= heater_cooldown_seconds):

            print(f"온도 낮음 ({sensor['temp']}°C < 목표 {crop_settings['temp'] - 2}°C) → 히터 작동")
            threading.Thread(target=heater_routine).start()
            last_heat_time = now
            last_temp_check_timestamp = sensor['timestamp']

        # 쿨러 조건
        elif sensor['temp'] > crop_settings['temp'] + 2:
            print(f"온도 높음 ({sensor['temp']}°C > 목표 {crop_settings['temp'] + 2}°C) → 쿨러 작동")
            control_device('CoolerA', 0); control_device('CoolerB', 0)
        else:
            if state[pins['CoolerA']] == 0 or state[pins['CoolerB']] == 0:
                print(f"온도 적정 ({sensor['temp']}°C) → 쿨러 꺼짐")
                control_device('CoolerA', 1); control_device('CoolerB', 1)

        time.sleep(10)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {crop_name} 제어 루프 종료됨.")
