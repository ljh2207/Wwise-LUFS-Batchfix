```
================================================================
  Wwise LUFS BatchFix - 설치 및 적용 가이드
================================================================
  다른 Wwise 프로젝트에서 동일한 툴을 사용하기 위한 안내서
================================================================


【 개요 】
────────────────────────────────────────────────────────────────
Wwise Authoring Tool의 Tools 메뉴에서 실행하는 LUFS 측정 도구.
Wwise에서 선택한 Sound 오브젝트(또는 컨테이너)의 원본 WAV 파일에
대해 Integrated LUFS, Sample Peak, RMS, 채널 수, 길이를 측정하고
표로 표시합니다.


【 파일 구성 】
────────────────────────────────────────────────────────────────
C:\Users\ljh2207\Wwise LUFS BatchFix\
  ├── main.py              ← 메인 소스코드 (tkinter 기반 GUI)
  ├── launch.bat           ← Wwise Add-on에서 호출하는 실행 스크립트
  ├── config.json          ← 창 위치/크기 자동 저장 (자동 생성)
  └── .venv\               ← Python 가상환경

%APPDATA%\Audiokinetic\Wwise\Add-ons\Commands\
  └── WwiseLUFSBatchFix.json  ← Wwise 메뉴 등록 파일


【 사전 요구사항 】
────────────────────────────────────────────────────────────────
1. Python 3.10 이상 설치
2. Wwise에서 WAAPI 활성화:
     Project > User Preferences > Enable Wwise Authoring API (WAAPI)
     포트: 8080 (기본값)


【 새 PC에 설치하는 방법 】
────────────────────────────────────────────────────────────────

[1단계] 툴 폴더 복사
  "Wwise LUFS BatchFix" 폴더 전체를 원하는 경로에 복사.
  (예: C:\Users\<사용자명>\Wwise LUFS BatchFix\)

[2단계] 가상환경 생성 및 패키지 설치
  cmd 또는 PowerShell에서 아래 명령 실행:

    cd "C:\Users\<사용자명>\Wwise LUFS BatchFix"
    python -m venv .venv
    .venv\Scripts\pip install soundfile pyloudnorm numpy waapi-client

[3단계] launch.bat 경로 수정
  launch.bat 파일을 메모장으로 열어 경로를 실제 설치 경로로 수정:

    @echo off
    cd /d "C:\Users\<사용자명>\Wwise LUFS BatchFix"
    start "" ".venv\Scripts\pythonw.exe" main.py

[4단계] Wwise Add-on 등록 파일 생성
  아래 경로에 WwiseLUFSBatchFix.json 파일 생성:
    %APPDATA%\Audiokinetic\Wwise\Add-ons\Commands\WwiseLUFSBatchFix.json

  파일 내용:
    {
        "version": 1,
        "commands": [
            {
                "id": "com.tools.wwise-lufs-meter",
                "displayName": "LUFS BatchFix",
                "program": "C:\\Users\\<사용자명>\\Wwise LUFS BatchFix\\launch.bat",
                "mainMenu": {
                    "basePath": "Tools"
                }
            }
        ]
    }

  ※ <사용자명>을 실제 Windows 사용자 이름으로 교체할 것.

[5단계] Wwise에서 Add-on 갱신
  Wwise가 실행 중이라면 재시작하거나, 아래 WAAPI 커맨드 실행:
    ReloadCommandAddons


【 사용 방법 】
────────────────────────────────────────────────────────────────
1. Wwise에서 측정할 오브젝트 선택
   - Sound 오브젝트: 해당 파일 1개 측정
   - Random/Blend/Property Container 등: 하위 모든 Sound 재귀 측정
   - 여러 오브젝트 동시 선택 가능

2. Wwise 메뉴 > Tools > LUFS BatchFix 클릭

3. LUFS BatchFix 창이 열리면 [측정] 버튼 클릭

4. 결과 확인
   - Integrated LUFS: EBU R128 기준 통합 라우드니스
   - Sample Peak: 파형 최대값 (dBFS)
   - Ch: 채널 수 / Duration: 파일 길이

5. [TSV 복사] 버튼으로 결과를 클립보드에 복사 → Excel 붙여넣기 가능


【 측정 결과 색상 기준 (LUFS) 】
────────────────────────────────────────────────────────────────
  빨강  (#ef5350)  > -6 LUFS       과도하게 큰 소리
  주황  (#ffa726)  -6 ~ -12 LUFS   높음
  초록  (#66bb6a)  -12 ~ -30 LUFS  적정 범위
  파랑  (#42a5f5)  < -30 LUFS      낮음
  노랑  (#ffcc02)  1초 미만 파일   LUFS 측정 불가 → RMS 표시


【 1초 미만 파일 처리 】
────────────────────────────────────────────────────────────────
EBU R128 LUFS-I 측정은 최소 약 400ms 이상의 오디오가 필요하며,
1초 미만 파일은 결과가 부정확합니다.
→ 1초 미만 파일은 LUFS 측정을 건너뛰고 Sample Peak + RMS 만 표시.
→ Integrated LUFS 칸에 "⚠ RMS -XX.X dB" 형식으로 표기.


【 창 위치/크기 저장 】
────────────────────────────────────────────────────────────────
창을 닫을 때 "Wwise LUFS BatchFix\config.json"에 위치와 크기가 자동 저장되어
다음 실행 시 동일한 상태로 복원됩니다.


【 주요 기술 스택 】
────────────────────────────────────────────────────────────────
  GUI        : Python tkinter (GPU 가속 없음 — 안정성 우선)
  LUFS 측정  : pyloudnorm (EBU R128)
  파일 읽기  : soundfile (libsndfile)
  Wwise 연동 : waapi-client (WAAPI WebSocket ws://127.0.0.1:8080)
  Wwise 연결 : ak.wwise.ui.getSelectedObjects
               ak.wwise.core.object.get (WAQL)


【 트러블슈팅 】
────────────────────────────────────────────────────────────────
증상: "Wwise에 연결할 수 없습니다"
→ Wwise가 실행 중인지 확인
→ Project > User Preferences > Enable WAAPI 체크 확인
→ 포트 8080이 방화벽에 막혀 있지 않은지 확인

증상: "waapi-client 미설치"
→ .venv\Scripts\pip install waapi-client 재실행

증상: "파일 없음"
→ Wwise Originals 폴더에 원본 WAV가 있는지 확인
→ 프로젝트 경로가 변경된 경우 Wwise에서 소스 파일 재연결 필요

증상: 메뉴에 LUFS BatchFix가 표시되지 않음
→ WwiseLUFSBatchFix.json 내 program 경로 확인 (역슬래시 이스케이프: \\)
→ Wwise 재시작 또는 ReloadCommandAddons 실행


================================================================
  작성일: 2026-04-10
================================================================
```
