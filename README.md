## 설치 방법

### 1. Python 설치 (3.11 이상)
### 2. 프로젝트 다운로드 및 설치
```bash
git clone https://github.com/kimh-code/aha-reaction-program.git
cd aha-reaction-program  
poetry install
```
### 3. 실행
```bash
poetry run python main.py
```
### 4. 폴더구조 및 사운드 파일 추가
```
aha-reaction-program
├── aha/ # '아하' 유레카 순간에 받고 싶은 반응 사운드들
├── ambient/ # ambient mode에 듣고 싶은 조용한 음악들
├── but/ # '근데...' 반응 사운드들
├── confused/ # '무슨말이야?' 혼란스러울 때 반응 사운드들
├── crazy/ # '미친' 순간에 받고 싶은 반응 사운드들
├── hmm/ # '흠...' 고민할 때 사운드들
├── lol/ # 'ㅋㅋㅋ' 웃는 사운드들
├── no/ # '아니' 거부 사운드들
├── work/ # 일 재촉 사운드들
├── wow/ # '와우' 놀람 사운드들
├── yeah/ # '오예' 환호 사운드들
├── .gitignore
├── main.py
├── poetry.lock
├── pyproject.toml
└── README.md
```

### 5. 지원하는 오디오 형식
.mp3, .wav, .ogg, .m4a
