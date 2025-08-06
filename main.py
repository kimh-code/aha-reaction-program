import pygame
import threading
import time
import os
import random
from collections import deque
from pynput import keyboard

# 추가: 오디오 파일 길이 측정용
try:
    import wave
    import contextlib
    WAVE_SUPPORT = True
except ImportError:
    WAVE_SUPPORT = False

# 오디오 파일 길이 측정을 위한 라이브러리
try:
    from pydub import AudioSegment
    import math
    PYDUB_SUPPORT = True
    print(">> pydub 지원: 다양한 오디오 형식 길이 측정 가능")
except ImportError:
    PYDUB_SUPPORT = False
    print("-- pydub 없음: WAV 파일만 정확한 길이 측정 (기타 형식은 5초 추정)")

class AhaReactionProgram:
    def __init__(self):
        # pygame 초기화
        pygame.mixer.init()
       
        # 최근 타이핑 기록 (최근 15글자에서 매칭)
        self.recent_keys = deque(maxlen=15)
       
        # 반응 사운드 파일 목록들
        self.sound_folders = {
            'aha': {'folder': 'aha/', 'patterns': [ 'dkgk', 'akwsp', 'akwdk', 'aha'], 'files': []},  # 아하, 맞네, 맞아
            'crazy': {'folder': 'crazy/', 'patterns': [ 'alcls', 'crazy'], 'files': []}, # 미친
            'wow': {'folder': 'wow/', 'patterns': [ 'dhk', 'dndhk', 'dh', 'eoqkr', 'gjf', 'wow'], 'files': []}, # 와, 우와, 오, 대박, 헐
            'yeah': {'folder': 'yeah/', 'patterns': [ 'dP~', 'dhdP', 'dPtm', 'dptm', 'yes', 'whgdk', 'yeah', 'yes'], 'files': []}, # 예~, 오예, 예스, 에스, 좋아
            'no': {'folder': 'no/', 'patterns': [ 'dksl', 'dkseho', 'dpdl', 'no', 'never'], 'files': []}, # 아니, 안돼, 에이
            'hmm': {'folder': 'hmm/', 'patterns': [ 'dma', 'gma', 'dj...', 'dj..', 'umm', 'hmm'], 'files': []}, # 음, 흠, 어...
            'lol': {'folder': 'lol/', 'patterns': ['ㅋㅋㅋ', 'ㅋㅋ', 'zzz' ,'zz' ,'kkk', 'kk', 'lol', 'gkgk', 'glgl', 'gpgp', 'dntru', 'dntrlek'], 'files': []},  # 하하, 히히, 헤헤, 웃겨, 웃기다
            'confused': {'folder': 'confused/', 'patterns': [ 'antmsakfdldi', 'dlgodksrk', 'ahfmrpTek' , 'ahfmrpTdj' , 'anjfRk' , 'anjdi', 'anjrk', 'gjr', 'what'], 'files': []}, # 무슨말이야, 이해안가, 모르겠다, 모르겠어, 뭘까, 뭐야, 뭐가, 헉
            'but': {'folder': 'but/', 'patterns': [ 'rmsep', 'rmfjgwlaks' , 'rmfjsk' ,'but', 'well', 'anyway', 'btw'], 'files': []}, # 근데, 그렇지만, 그러나
            'work': {'folder': 'work/', 'patterns': [], 'files': []}  # 타이머 전용, 패턴 없음
        }
       
        # 볼륨 설정 (0.0 ~ 1.0) - 폴더별로 설정
        self.volume_settings = {
            'aha': 0.5,
            'crazy': 0.5,
            'wow': 0.5,
            'yeah': 0.5,
            'no': 0.5,
            'hmm': 0.5,
            'lol': 0.5,
            'confused': 0.5,
            'but': 0.5,
            'work': 0.9,  # 일 재촉은 좀 크게
            'ambient': 0.1
        }
       
        # 타이머 관련 설정
        self.last_typing_time = time.time()
        self.work_reminder_interval = 180  # 3분 (180초)
        self.work_timer_thread = None
        self.work_timer_active = True
       
        # 폴더별 스레드 관리 (같은 폴더는 단일, 다른 폴더는 멀티)
        self.folder_threads = {}  # {folder_key: thread_object}
        self.folder_start_times = {}  # {folder_key: start_time} 재생 시작 시간 추적
        self.folder_last_reaction_times = {}  # {folder_key: last_reaction_time} 마지막 반응 시점 추적
        self.folder_extend_flags = {}  # {folder_key: extend_seconds} 연장 시간
       
        # 모드 설정 (0: 무음, 1: ambient music)
        self.background_mode = 0
        self.is_running = True
        self.ambient_thread = None
        self.ambient_playing = False
        self.ambient_paused = False  # ambient 일시정지 상태
       
        # ambient 음악 파일 목록
        self.ambient_files = []
       
        # 오디오 파일 확인
        self.check_audio_files()
       
        # 일 재촉 타이머 시작
        self.start_work_timer()
       
    def get_audio_duration(self, file_path):
        """오디오 파일의 길이를 초 단위로 반환"""
        try:
            if WAVE_SUPPORT and file_path.lower().endswith('.wav'):
                with contextlib.closing(wave.open(file_path, 'r')) as f:
                    frames = f.getnframes()
                    rate = f.getframerate()
                    duration = frames / float(rate)
                    return duration
            elif PYDUB_SUPPORT:
                audio = AudioSegment.from_file(file_path)
                return len(audio) / 1000.0  # milliseconds to seconds
            else:
                # 기본값으로 5초 반환 (정확하지 않지만 안전)
                return 5.0
        except Exception as e:
            print(f"오디오 길이 측정 오류 ({os.path.basename(file_path)}): {e}")
            return 5.0  # 기본값
       
    def check_audio_files(self):
        """필요한 오디오 파일들이 있는지 확인"""
        print("=" * 60)
        print("*** 오디오 파일 확인 ***")
       
        # 🔍 디버깅: 현재 위치와 폴더 내용 출력
        current_dir = os.getcwd()
        print(f"🔍 현재 작업 디렉토리: {current_dir}")
        print(f"🔍 현재 폴더 내용: {os.listdir('.')}")
       
        # 특정 폴더들 존재 여부 직접 확인
        for folder in ['aha', 'crazy', 'ambient']:
            exists = os.path.exists(folder)
            is_dir = os.path.isdir(folder) if exists else False
            print(f"🔍 {folder} 폴더: 존재={exists}, 디렉토리={is_dir}")
        print("=" * 60)
       
        # 지원하는 음악 파일 확장자
        supported_formats = ['.wav', '.mp3', '.ogg', '.m4a']
       
        # 모든 반응 사운드 폴더들 확인
        for folder_key, folder_info in self.sound_folders.items():
            folder_path = folder_info['folder']
            folder_name = folder_path.rstrip('/')
           
            if os.path.exists(folder_name) and os.path.isdir(folder_name):
                print(f">> {folder_name} 폴더 발견")
               
                # 폴더 안의 모든 파일 확인
                for file in os.listdir(folder_name):
                    file_path = os.path.join(folder_name, file)
                    if os.path.isfile(file_path):
                        _, ext = os.path.splitext(file.lower())
                        if ext in supported_formats:
                            folder_info['files'].append(file_path)
               
                if folder_info['files']:
                    print(f">> {folder_name} 폴더에서 {len(folder_info['files'])}개의 반응 사운드 발견:")
                    for file in folder_info['files'][:3]:  # 최대 3개만 표시
                        print(f"   - {os.path.basename(file)}")
                    if len(folder_info['files']) > 3:
                        print(f"   ... 그 외 {len(folder_info['files']) - 3}개 파일")
                   
                    # 지원 패턴들 표시 (work 폴더는 패턴 없음)
                    if folder_info['patterns']:
                        patterns_str = ", ".join([f"'{p}'" for p in folder_info['patterns']])
                        print(f"   패턴: {patterns_str}")
                else:
                    print(f"-- {folder_name} 폴더에 사운드 파일이 없습니다.")
            else:
                print(f"-- {folder_name} 폴더가 없습니다.")
            print()
       
        # ambient 폴더 및 음악 파일들 확인
        if os.path.exists('ambient') and os.path.isdir('ambient'):
            print(">> ambient 폴더 발견")
           
            # ambient 폴더 안의 모든 파일 확인
            for file in os.listdir('ambient'):
                file_path = os.path.join('ambient', file)
                if os.path.isfile(file_path):
                    _, ext = os.path.splitext(file.lower())
                    if ext in supported_formats:
                        self.ambient_files.append(file_path)
           
            if self.ambient_files:
                print(f">> ambient 폴더에서 {len(self.ambient_files)}개의 음악 파일 발견:")
                for file in self.ambient_files[:3]:  # 최대 3개만 표시
                    print(f"   - {os.path.basename(file)}")
                if len(self.ambient_files) > 3:
                    print(f"   ... 그 외 {len(self.ambient_files) - 3}개 파일")
            else:
                print("-- ambient 폴더에 음악 파일이 없습니다.")
        else:
            print("-- ambient 폴더가 없습니다. ambient music 기능을 사용할 수 없습니다.")
       
        print()
       
    def start_work_timer(self):
        """일 재촉 타이머 시작"""
        if self.sound_folders['work']['files']:  # work 폴더에 파일이 있을 때만
            self.work_timer_active = True
            self.work_timer_thread = threading.Thread(target=self._work_timer_loop, daemon=True)
            self.work_timer_thread.start()
            print("⏰ 일 재촉 타이머 활성화! (3분 후 첫 알림)")
       
    def stop_all_folder_threads(self):
        """모든 폴더 스레드 중지"""
        for folder_key in list(self.folder_threads.keys()):
            self.stop_folder_thread(folder_key)
        print("-- 모든 반응 사운드 중지")
       
    def stop_work_timer(self):
        """일 재촉 타이머 정지"""
        self.work_timer_active = False
       
    def _work_timer_loop(self):
        """일 재촉 타이머 루프"""
        try:
            while self.work_timer_active and self.is_running:
                time.sleep(1)  # 1초마다 체크
               
                # 마지막 타이핑으로부터 3분 이상 지났는지 확인
                if (time.time() - self.last_typing_time >= self.work_reminder_interval and
                    self.work_timer_active):
                   
                    # 일 재촉 사운드 재생
                    work_files = self.sound_folders['work']['files']
                    if work_files:
                        print("⏰ 3분간 타이핑이 없었습니다! 일하세요!")
                        self.play_reaction_sound('work', work_files)
                       
                        # 다음 알림을 위해 시간 업데이트 (1분 후 다시 알림)
                        self.last_typing_time = time.time() - (self.work_reminder_interval - 60)
                       
        except Exception as e:
            print(f"일 재촉 타이머 오류: {e}")
   
    def get_folder_emoji(self, folder_key):
        """폴더별 이모지 반환"""
        emoji_map = {
            'aha': '>>',
            'crazy': '!!',
            'wow': '😮',
            'yeah': '🎉',
            'no': '❌',
            'hmm': '🤔',
            'lol': '😂',
            'confused': '❓',
            'but': '↔️',
            'work': '⏰'
        }
        return emoji_map.get(folder_key, '🎵')
       
    def stop_folder_thread(self, folder_key):
        """특정 폴더의 스레드 중지"""
        if folder_key in self.folder_threads:
            thread = self.folder_threads[folder_key]
            if thread and thread.is_alive():
                # 스레드에 중지 신호 전송 (스레드가 체크할 수 있도록)
                if hasattr(thread, 'stop_flag'):
                    thread.stop_flag = True
                print(f"-- {folder_key} 폴더의 이전 반응 중지")
            del self.folder_threads[folder_key]
           
        # 시간 추적 정보도 정리
        if folder_key in self.folder_start_times:
            del self.folder_start_times[folder_key]
        if folder_key in self.folder_last_reaction_times:
            del self.folder_last_reaction_times[folder_key]
        if folder_key in self.folder_extend_flags:
            del self.folder_extend_flags[folder_key]
   
    def extend_folder_reaction(self, folder_key):
        """새로운 반응에 대해 직전 반응 시점부터의 경과 시간만큼 연장"""
        if folder_key in self.folder_start_times and folder_key in self.folder_threads:
            current_time = time.time()
           
            # 마지막 반응 시점 가져오기 (없으면 시작 시점)
            last_reaction_time = self.folder_last_reaction_times.get(folder_key, self.folder_start_times[folder_key])
           
            # 마지막 반응 시점부터의 경과 시간 계산
            elapsed_since_last = current_time - last_reaction_time
           
            if elapsed_since_last > 0.5:  # 최소 0.5초 이후에만 연장 (너무 빠른 연장 방지)
                extend_seconds = elapsed_since_last
                self.folder_extend_flags[folder_key] = self.folder_extend_flags.get(folder_key, 0) + extend_seconds
               
                # 마지막 반응 시점 업데이트
                self.folder_last_reaction_times[folder_key] = current_time
               
                emoji = self.get_folder_emoji(folder_key)
                total_time = 5.0 + self.folder_extend_flags[folder_key]
                print(f"{emoji} {folder_key} 반응 연장! (+{extend_seconds:.1f}초, 총 {total_time:.1f}초)")
                return True
           
        return False
       
    def play_reaction_sound(self, folder_key, sound_files):
        """통합 반응 사운드 재생 함수 (폴더별 단일 스레드 + 연장 시스템)"""
        try:
            if sound_files:
                # 같은 폴더에서 이미 재생 중인지 확인
                if folder_key in self.folder_threads and self.folder_threads[folder_key].is_alive():
                    # 기존 반응 연장 시도
                    if self.extend_folder_reaction(folder_key):
                        return  # 연장 성공하면 새 스레드 생성하지 않음
                    else:
                        # 연장할 시간이 없으면 기존 방식대로 중단하고 새로 시작
                        self.stop_folder_thread(folder_key)
               
                # Ambient 모드에서 배경음악이 재생 중이면 일시정지
                if self.background_mode == 1 and self.ambient_playing and not self.ambient_paused:
                    pygame.mixer.music.pause()
                    self.ambient_paused = True
               
                emoji = self.get_folder_emoji(folder_key)
                print(f"{emoji} {folder_key.upper()} 반응 시작! (5초 연속 재생)")
               
                # 시작 시간 기록
                self.folder_start_times[folder_key] = time.time()
                self.folder_last_reaction_times[folder_key] = time.time()  # 마지막 반응 시점도 초기화
                self.folder_extend_flags[folder_key] = 0  # 연장 시간 초기화
               
                # 새로운 스레드 생성 (중지 플래그 포함)
                sound_thread = threading.Thread(
                    target=self._play_continuous_sounds,
                    args=(sound_files, emoji, folder_key),
                    daemon=True
                )
                sound_thread.stop_flag = False  # 중지 플래그 추가
                sound_thread.start()
               
                # 폴더별 스레드 딕셔너리에 저장
                self.folder_threads[folder_key] = sound_thread
                   
            else:
                print(f"{folder_key} 폴더에 사운드 파일이 없어서 재생할 수 없습니다.")
        except Exception as e:
            print(f"{folder_key} 반응 사운드 재생 오류: {e}")
           
    def play_clap_sound(self):
        """aha 폴더에서 5초 동안 연속으로 랜덤 사운드 재생 (하위 호환성)"""
        aha_files = self.sound_folders['aha']['files']
        self.play_reaction_sound('aha', aha_files)
           
    def play_crazy_sound(self):
        """crazy 폴더에서 5초 동안 연속으로 랜덤 사운드 재생 (하위 호환성)"""
        crazy_files = self.sound_folders['crazy']['files']
        self.play_reaction_sound('crazy', crazy_files)
           
    def _play_continuous_sounds(self, sound_files, emoji, folder_key):
        """5초 동안 랜덤 파일의 랜덤 구간을 연속 재생 (폴더별 볼륨 적용 + 연장 시스템)"""
        import time
        start_time = time.time()
        current_thread = threading.current_thread()
       
        # 현재 재생 중인 폴더의 볼륨 설정
        current_volume = self.volume_settings.get(folder_key, 0.7)
       
        try:
            while True:
                # 기본 5초 + 연장된 시간 계산
                base_duration = 5.0
                extended_time = self.folder_extend_flags.get(folder_key, 0)
                total_duration = base_duration + extended_time
               
                elapsed = time.time() - start_time
               
                # 총 재생 시간 초과하면 종료
                if elapsed >= total_duration:
                    break
               
                # 중지 플래그 체크 (같은 폴더에서 새 반응이 오면 중지)
                if hasattr(current_thread, 'stop_flag') and current_thread.stop_flag:
                    print(f"{emoji} {folder_key} 반응 중지됨 (새로운 반응으로 인해)")
                    break
               
                # 랜덤 파일 선택
                selected_file = random.choice(sound_files)
               
                # 파일 길이 확인
                file_duration = self.get_audio_duration(selected_file)
               
                # 랜덤 시작 지점 선택 (전체 길이의 80% 내에서)
                max_start = max(0, file_duration - 2.0)  # 최소 2초는 재생하도록
                random_start = random.uniform(0, max_start) if max_start > 0 else 0
               
                # 연장 정보 표시  
                total_duration = base_duration + extended_time
                remaining = total_duration - elapsed
                extend_info = f" (총 {total_duration:.1f}초)" if extended_time > 0 else ""
                print(f"{emoji} 재생: {os.path.basename(selected_file)} ({random_start:.1f}초부터, 남은시간: {remaining:.1f}초{extend_info})")
               
                # 사운드 로드 및 볼륨 설정
                current_sound = pygame.mixer.Sound(selected_file)
                current_sound.set_volume(current_volume)  # 폴더별 볼륨 적용
                current_sound.play()
               
                # 랜덤 시간 재생 (1-3초) - 중지 플래그 체크하면서
                play_duration = random.uniform(1.0, 3.0)
                sleep_time = 0
                while sleep_time < play_duration:
                    # 연장 플래그 업데이트 확인 (실시간으로 연장 시간 반영)
                    current_extended = self.folder_extend_flags.get(folder_key, 0)
                    if current_extended != extended_time:
                        extended_time = current_extended
                        total_duration = base_duration + extended_time
                        print(f"{emoji} 실시간 연장 반영! 총 재생시간: {total_duration:.1f}초")
                   
                    if hasattr(current_thread, 'stop_flag') and current_thread.stop_flag:
                        current_sound.stop()  # 현재 사운드도 중지
                        print(f"{emoji} {folder_key} 반응 즉시 중지")
                        return
                    time.sleep(0.1)
                    sleep_time += 0.1
               
                # 현재 사운드 중지
                current_sound.stop()
               
                # 짧은 간격 - 중지 플래그 체크
                if hasattr(current_thread, 'stop_flag') and current_thread.stop_flag:
                    break
                time.sleep(0.1)
           
            # 모든 사운드 중지
            pygame.mixer.stop()
           
        except Exception as e:
            print(f"연속 사운드 재생 오류: {e}")
        finally:
            # 완료된 스레드를 딕셔너리에서 제거
            if folder_key in self.folder_threads:
                del self.folder_threads[folder_key]
            if folder_key in self.folder_start_times:
                del self.folder_start_times[folder_key]
            if folder_key in self.folder_last_reaction_times:
                del self.folder_last_reaction_times[folder_key]
            if folder_key in self.folder_extend_flags:
                del self.folder_extend_flags[folder_key]
               
            # Ambient 모드에서 일시정지된 상태라면 배경음악 재개 (무음모드가 아닐 때만)
            if (self.ambient_paused and self.ambient_playing and
                self.background_mode == 1 and self.is_running):
                pygame.mixer.music.unpause()
                self.ambient_paused = False
                print(">> 배경음악 재개")
            else:
                print(f"-- {folder_key} 반응 소리 완료")
   
    def on_key_press(self, key):
        """키가 눌렸을 때 호출되는 함수"""
        try:
            # 타이핑 시간 업데이트 (일 재촉 타이머용)
            self.last_typing_time = time.time()
           
            # 일반 문자 키인 경우
            if hasattr(key, 'char') and key.char:
                print(f"🔍 키 입력: '{key.char}'")  # 디버깅
                self.recent_keys.append(key.char)
               
                # 각 폴더의 패턴들을 확인 (work 폴더는 제외)
                recent_text = ''.join(self.recent_keys)
                print(f"🔍 최근 입력: '{recent_text}'")  # 디버깅
               
                for folder_key, folder_info in self.sound_folders.items():
                    if folder_key == 'work':  # work 폴더는 타이머로만 작동
                        continue
                       
                    for pattern in folder_info['patterns']:
                        if recent_text.endswith(pattern):
                            if folder_info['files']:  # 파일이 있는 경우만
                                print(f"🔍 '{pattern}' 패턴 감지! ({folder_key} 폴더)")
                                self.play_reaction_sound(folder_key, folder_info['files'])
                                emoji = self.get_folder_emoji(folder_key)
                                print(f"{emoji} {folder_key.upper()}! 반응 사운드 재생!")
                                return  # 하나 발견하면 더 이상 확인하지 않음
                   
            # 특수 키 처리
            elif key == keyboard.Key.f1:
                print("🔍 F1 키 감지!")
                self.toggle_background_mode()
            elif key == keyboard.Key.esc:
                print("프로그램을 종료합니다...")
                self.is_running = False
                self.stop_work_timer()  # 타이머도 정지
                self.stop_all_folder_threads()  # 모든 폴더 스레드 정지
                return False
               
        except AttributeError:
            # 특수 키의 경우 무시
            print(f"🔍 특수 키: {key}")
            pass
           
    def toggle_background_mode(self):
        """배경 모드 전환 (무음 ↔ ambient music)"""
        self.background_mode = 1 - self.background_mode
       
        if self.background_mode == 0:
            print("-- 무음 모드로 전환")
            self.stop_ambient_music()
            # 혹시 일시정지 상태였다면 그것도 해제
            if self.ambient_paused:
                self.ambient_paused = False
                print("-- 일시정지 상태도 해제")
        else:
            print(">> Ambient Music 모드로 전환")
            self.start_ambient_music()
           
    def start_ambient_music(self):
        """ambient music 시작"""
        if self.ambient_files and not self.ambient_playing:
            self.ambient_playing = True
            # ambient 볼륨 적용
            pygame.mixer.music.set_volume(self.volume_settings['ambient'])
            self.ambient_thread = threading.Thread(target=self._play_ambient_loop, daemon=True)
            self.ambient_thread.start()
           
    def stop_ambient_music(self):
        """ambient music 정지"""
        self.ambient_playing = False
        self.ambient_paused = False  # 일시정지 상태도 초기화
        pygame.mixer.stop()  # Sound 객체들 정지
        pygame.mixer.music.stop()  # Music 스트림 정지
        print("-- 배경음악 완전 정지")
       
    def _play_ambient_loop(self):
        """ambient music을 랜덤으로 반복 재생하는 내부 함수"""
        try:
            while self.ambient_playing and self.is_running:
                if self.ambient_files and not self.ambient_paused:
                    # 랜덤으로 음악 파일 선택
                    selected_file = random.choice(self.ambient_files)
                    ambient_volume = int(self.volume_settings['ambient']*100)
                    print(f">> 배경음악: {os.path.basename(selected_file)} (볼륨: {ambient_volume}%)")
                   
                    pygame.mixer.music.load(selected_file)
                    pygame.mixer.music.play()
                   
                    # 음악이 끝날 때까지 대기 (일시정지 상태도 고려)
                    while pygame.mixer.music.get_busy() and self.ambient_playing:
                        time.sleep(0.1)
                        # 일시정지 중이면 계속 대기
                        while self.ambient_paused and self.ambient_playing:
                            time.sleep(0.1)
                   
                    # 잠깐 대기 후 다음 곡 재생 (일시정지 중이 아닐 때만)
                    if self.ambient_playing and not self.ambient_paused:
                        time.sleep(0.5)
                else:
                    time.sleep(0.1)
                       
        except Exception as e:
            print(f"Ambient music 재생 오류: {e}")
           
    def show_instructions(self):
        """사용법 안내"""
        print("=" * 60)
        print(">>> TYPING REACTION PROGRAM <<<")
        print("=" * 60)
        print("사용법:")
        print("  >> 다양한 감정 표현을 타이핑하면 해당 폴더에서 5초간 연속 랜덤 재생!")
        print()
        print("📁 지원하는 폴더별 패턴:")
        for folder_key, folder_info in self.sound_folders.items():
            if folder_key == 'work':  # work 폴더는 별도 설명
                continue
            patterns_str = ", ".join([f"'{p}'" for p in folder_info['patterns']])
            emoji = self.get_folder_emoji(folder_key)
            print(f"   {emoji} {folder_key}/ 폴더: {patterns_str}")
        print()
        print("⏰ 특별 기능:")
        print("   ⏰ work/ 폴더: 3분간 타이핑이 없으면 자동으로 일 재촉 사운드 재생!")
        print("   (1분마다 반복 알림)")
        print()
        print("  >> F1: 무음모드 <-> Ambient Music 모드 전환")
        print("  >> ESC: 프로그램 종료")
        print()
        print("💡 한글 입력 시 영어 키보드 패턴으로 자동 인식합니다!")
        print("   - 한글로 타이핑해도 영어 키 입력으로 감지되어 문제없이 작동합니다")
        print()
        print("볼륨 설정:")
        for folder_key, volume in self.volume_settings.items():
            if folder_key in self.sound_folders:
                print(f"  >> {folder_key} 폴더: {int(volume*100)}%")
            elif folder_key == 'ambient':
                print(f"  >> {folder_key} 폴더: {int(volume*100)}%")
        print("  (코드에서 volume_settings 딕셔너리로 조절 가능)")
        print()
        print("연속 재생 방식:")
        print("  >> 5초 동안 여러 개의 사운드가 연속으로 랜덤 재생됩니다")
        print("  >> 같은 폴더: 새로운 패턴 감지시 기존 반응 시간을 연장 (최대 5초)")
        print("  >> 다른 폴더: 여러 감정을 동시에 표현 가능 (멀티 스레드)")
        print("  >> Ambient 모드에서는 반응 소리 동안 배경음악이 일시정지됩니다")
        print()
        print("🎭 감정 표현 예시:")
        print("  >> 00:00 '오' → 5초 시작, 00:01 '와' → +1초 연장 (총 6초)")
        print("  >> 00:05 '헐' → +4초 연장, 00:08 '우와' → +3초 연장 (총 13초)")
        print("  >> '아하' + '미친': 두 감정이 동시에 재생!")
        print("  >> 연장 계산: 직전 반응 시점부터의 시차만큼 연장")
        print()
        print("필요한 폴더 구조:")
        print("  >> aha/ 폴더 - '아하' 관련 반응 사운드들")
        print("  >> crazy/ 폴더 - '미친' 관련 반응 사운드들")
        print("  >> wow/ 폴더 - '와', '헐' 관련 놀람 사운드들")
        print("  >> yeah/ 폴더 - '오예', '좋아' 관련 환호 사운드들")
        print("  >> no/ 폴더 - '아니', '안돼' 관련 거부 사운드들")
        print("  >> hmm/ 폴더 - '음', '흠' 관련 고민 사운드들")
        print("  >> lol/ 폴더 - 'ㅋㅋㅋ', '하하' 관련 웃음 사운드들")
        print("  >> confused/ 폴더 - '무슨말이야', '이해안가' 관련 혼란 사운드들")
        print("  >> but/ 폴더 - '근데', '그렇지만' 관련 전환 사운드들")
        print("  >> work/ 폴더 - 일 재촉 사운드들 (3분 무활동시 자동 재생)")
        print("  >> ambient/ 폴더 - 배경음악들")
        print("  >> 지원 형식: .wav, .mp3, .ogg, .m4a")
        print()
        current_mode = "무음 모드" if self.background_mode == 0 else "Ambient Music 모드"
        print(f"현재 모드: [{current_mode}]")
        print("프로그램이 실행 중입니다... 타이핑을 시작하세요!")
        print("=" * 60)
       
    def run(self):
        """프로그램 실행"""
        self.show_instructions()
       
        # 키보드 리스너 시작
        with keyboard.Listener(on_press=self.on_key_press) as listener:
            try:
                while self.is_running:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n프로그램이 중단되었습니다.")
            finally:
                self.stop_ambient_music()
                self.stop_work_timer()  # 일 재촉 타이머도 정지
                self.stop_all_folder_threads()  # 모든 폴더 스레드 정지
                listener.stop()

if __name__ == "__main__":
    try:
        program = AhaReactionProgram()
        program.run()
    except Exception as e:
        print(f"프로그램 실행 오류: {e}")
        print("pygame과 pynput 라이브러리가 설치되어 있는지 확인해주세요:")
        print("pip install pygame pynput")