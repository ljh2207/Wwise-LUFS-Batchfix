# Wwise LUFS BatchFix

Wwise Authoring Tool의 **Tools 메뉴**에서 실행하는 LUFS 측정 및 수정 도구.  
선택한 Sound 오브젝트(또는 컨테이너)의 원본 WAV 파일에 대해 **Integrated LUFS, Sample Peak, RMS, 채널 수, 길이**를 측정하고 표로 표시합니다.
볼륨 적용을 통해 Target LUFS로 볼륨을 수정합니다.
<img width="1217" height="743" alt="image" src="https://github.com/user-attachments/assets/332fff75-24ae-4788-a208-a114346c7e28" />


---

## 목차

- [사전 요구사항](#사전-요구사항)
- [설치 방법](#설치-방법)
- [사용 방법](#사용-방법)
- [측정 결과 색상 기준](#측정-결과-색상-기준)
- [1초 미만 파일 처리](#1초-미만-파일-처리)
- [멀티채널 파일 처리](#멀티채널-파일-처리)
- [트러블슈팅](#트러블슈팅)
- [기술 스택](#기술-스택)

---

## 사전 요구사항

- Python 3.10 이상
- Wwise에서 WAAPI 활성화:  
  `Project > User Preferences > Enable Wwise Authoring API (WAAPI)` (포트: 8080)

---

## 설치 방법

### 1단계 — 저장소 클론

```bash
git clone https://github.com/ljh2207/Wwise-LUFS-Batchfix.git "Wwise LUFS BatchFix"
```

> 원하는 경로로 이동한 뒤 실행하세요.  
> 예: `C:\Users\<사용자명>\` 아래에 클론하면 `C:\Users\<사용자명>\Wwise LUFS BatchFix\` 폴더가 생성됩니다.

### 2단계 — 가상환경 생성 및 패키지 설치

```bash
cd "Wwise LUFS BatchFix"
python -m venv .venv
.venv\Scripts\pip install soundfile pyloudnorm numpy waapi-client
```

### 3단계 — launch.bat 경로 수정

`launch.bat`을 메모장으로 열어 경로를 실제 설치 경로로 수정합니다.

```bat
@echo off
cd /d "C:\Users\<사용자명>\Wwise LUFS BatchFix"
start "" ".venv\Scripts\pythonw.exe" main.py
```

### 4단계 — Wwise Add-on 등록 파일 생성

아래 경로에 `WwiseLUFSBatchFix.json` 파일을 생성합니다.

```
%APPDATA%\Audiokinetic\Wwise\Add-ons\Commands\WwiseLUFSBatchFix.json
```

```json
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
```

> `<사용자명>`을 실제 Windows 사용자 이름으로 교체하세요.  
> 경로 구분자는 `\\` (역슬래시 이스케이프)를 사용해야 합니다.

### 5단계 — Wwise에서 Add-on 갱신

Wwise가 실행 중이라면 재시작하거나, WAAPI 커맨드로 즉시 반영합니다.

```
ReloadCommandAddons
```

---

## 사용 방법

1. **Wwise에서 측정할 오브젝트 선택**
   - Sound 오브젝트: 해당 파일 1개 측정
   - Random / Blend / Property Container 등: 하위 모든 Sound 재귀 측정
   - 여러 오브젝트 동시 선택 가능

2. **Wwise 메뉴 → `Tools > LUFS BatchFix` 클릭**

3. **LUFS BatchFix 창이 열리면 `[측정]` 버튼 클릭**

4. **결과 확인**
   | 컬럼 | 설명 |
   |------|------|
   | Integrated LUFS | EBU R128 기준 통합 라우드니스 |
   | Sample Peak | 파형 최대값 (dBFS) |
   | Ch | 채널 수 |
   | Duration | 파일 길이 |

5. **볼륨 적용 대상 선택**
   - **✓ 열 클릭** — 해당 행 체크/해제
   - **헤더 ✓ 클릭** — 전체 체크/해제 토글
   - **Shift+클릭** — 마지막 체크 행 ~ 현재 행 범위 일괄 토글
   - 체크된 행이 없으면 Treeview 선택 행 기준, 선택도 없으면 전체 적용

6. **`[볼륨 적용]` 버튼으로 Target LUFS 정규화**
   - 우측 상단 Target 스핀박스에서 목표 LUFS 설정 (기본값 -14.0 LUFS)
   - `[볼륨 적용]` 클릭 시 `Volume = Target - Measured LUFS` 로 Sound 오브젝트의 Volume을 덮어씁니다
   - **※ 기존 Volume 값을 덮어씁니다**
   - `[Downmix]` 표시 파일은 정확도 문제로 볼륨 적용 건너뜀

7. **`[TSV 복사]` 버튼**으로 결과를 클립보드에 복사 → Excel 붙여넣기 가능

---

## 측정 결과 색상 기준

| 색상 | 범위 | 의미 |
|------|------|------|
| 🔴 빨강 `#ef5350` | > -6 LUFS | 과도하게 큰 소리 |
| 🟠 주황 `#ffa726` | -6 ~ -12 LUFS | 높음 |
| 🟢 초록 `#66bb6a` | -12 ~ -30 LUFS | 적정 범위 |
| 🔵 파랑 `#42a5f5` | < -30 LUFS | 낮음 |
| 🟡 노랑 `#ffcc02` | 1초 미만 파일 | LUFS 측정 불가 → RMS 표시 |

---

## 1초 미만 파일 처리

EBU R128 LUFS-I 측정은 최소 약 400ms 이상의 오디오가 필요하며, 1초 미만 파일은 결과가 부정확합니다.

- LUFS 측정을 건너뛰고 **Sample Peak + RMS만 표시**
- Integrated LUFS 칸에 `⚠ RMS -XX.X dB` 형식으로 표기

---

## 멀티채널 파일 처리

`pyloudnorm`이 네이티브로 지원하는 채널 수는 1ch, 2ch, 5ch, 6ch입니다.  
그 외 채널 수에 대해서는 ITU-R BS.775 계수로 스테레오 fold-down 후 측정합니다.

| 채널 수 | 처리 방식 |
|---------|-----------|
| 1ch, 2ch, 5ch, 6ch | 직접 측정 |
| 3ch (L R C) | `L' = L + 0.707×C`, `R' = R + 0.707×C` 로 fold-down 후 측정, `[Downmix]` 표시 |
| 4ch (L R Ls Rs) | `L' = L + 0.707×Ls`, `R' = R + 0.707×Rs` 로 fold-down 후 측정, `[Downmix]` 표시 |
| 7ch, 8ch 이상 | 채널 마스크 확인 불가 → 측정 불가 표시 |

`[Downmix]` 표시가 붙은 파일은 볼륨 적용 대상에서 제외됩니다.

---

## 트러블슈팅

| 증상 | 해결 방법 |
|------|-----------|
| "Wwise에 연결할 수 없습니다" | Wwise 실행 여부 확인 / `Enable WAAPI` 체크 / 포트 8080 방화벽 확인 |
| "waapi-client 미설치" | `.venv\Scripts\pip install waapi-client` 재실행 |
| "파일 없음" | Wwise Originals 폴더에 원본 WAV가 있는지 확인 / 소스 파일 재연결 |
| 메뉴에 LUFS BatchFix가 표시되지 않음 | `WwiseLUFSBatchFix.json` 내 `program` 경로 확인 / Wwise 재시작 또는 `ReloadCommandAddons` 실행 |

---

## 기술 스택

| 역할 | 라이브러리 / 도구 |
|------|------------------|
| GUI | Python `tkinter` |
| LUFS 측정 | `pyloudnorm` (EBU R128) |
| 파일 읽기 | `soundfile` (libsndfile) |
| Wwise 연동 | `waapi-client` (WebSocket `ws://127.0.0.1:8080`) |
| Wwise API | `ak.wwise.ui.getSelectedObjects`, `ak.wwise.core.object.get`, `ak.wwise.core.object.setProperty` |

---

## 파일 구성

```
Wwise LUFS BatchFix\
  ├── main.py        ← 메인 소스코드 (tkinter 기반 GUI)
  ├── launch.bat     ← Wwise Add-on에서 호출하는 실행 스크립트
  ├── README.md
  └── .venv\         ← Python 가상환경 (로컬 생성, git 미포함)

%APPDATA%\Audiokinetic\Wwise\Add-ons\Commands\
  └── WwiseLUFSBatchFix.json  ← Wwise 메뉴 등록 파일 (수동 생성)
```

> `config.json` (창 위치/크기 자동 저장)은 실행 시 자동 생성됩니다.
