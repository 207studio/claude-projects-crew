# Claude 데스크톱 앱 Projects(베타) 기능 개선 제안서

## 대상 기능 재확인
이 제안서가 다루는 것은 claude.ai 채팅의 기존 Projects(지식 파일·지침 기능)가 아니라, **Claude 데스크톱 앱 Code 탭 / claude.ai/code에 새로 나온 "Projects(공개 베타)"** 다. "한 대화(프로젝트)가 관련 작업 전체를 조율하며, 저장소·지침·메모리를 공유하는 여러 병렬 클라우드 세션(스레드)을 진행시키는" 기능으로, 각 스레드는 자기 브랜치에서 작업하고 필요하면 PR을 연다. Pro/Max 플랜에 점진적으로 롤아웃 중이며 Team/Enterprise는 아직 지원하지 않는다.
(원문: "A project is one ongoing conversation where Claude coordinates a stream of related work for you... Each thread is usually a cloud session... Projects are in public beta on Pro and Max plans and rolling out gradually..." / 출처: https://code.claude.com/docs/en/claude-projects)

기존 claude.ai 채팅의 Projects(지식 파일 업로드, 프로젝트 지침 등)는 별도 기능이며 참고용으로만 남긴다.
(출처: https://support.claude.com/en/articles/9517075-what-are-projects , https://support.claude.com/en/articles/9519189-manage-project-visibility-and-sharing)

## 배경

컴퓨터 사용(Computer use) 기능은 데스크톱 앱 설정(Settings > General)에서 켤 수 있으며, 앱 접근 승인은 세션 단위로 이루어진다.
(출처: https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork)

세션 기반 사용량 한도는 Pro/Max 플랜에서 5시간마다 리셋되며, Max 플랜은 별도의 주간 한도가 있다.
(출처: https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work)

클라우드 세션(Claude Code on the web 등)은 저장소를 새로 클론해서 시작하며, 커밋되지 않고 내 컴퓨터에만 설치·설정한 것(사용자 전역 CLAUDE.md, 사용자 전역 스킬, 로컬/사용자 범위로 추가한 MCP 서버, 대화형 로그인 등)은 세션에서 사용할 수 없다.
(출처: https://code.claude.com/docs/en/cloud-environments , "What carries over from your setup" 표)

클라우드 세션을 터미널로 가져오는 teleport는 해당 브랜치를 fetch/checkout하고 대화 기록을 불러오지만, 터미널은 그 세션의 "별도 사본"을 가지게 되어 이후 작업은 로컬에만 남고 클라우드 세션에는 반영되지 않는다. 반대 방향인 데스크톱 앱의 "Continue in" 메뉴도 브랜치를 push하고 대화 요약을 생성해 새 클라우드 세션을 만드는 방식이라, 실시간 연결이 아니라 파일·브랜치·요약의 일회성 이관이다.
(출처: https://code.claude.com/docs/en/claude-code-on-the-web , https://code.claude.com/docs/en/desktop)

또한 데스크톱 앱이 "다른 세션을 확인/메시지/보관"하는 화면은 데스크톱 앱이 직접 실행한 로컬·SSH·WSL 세션만 보여주며, 클라우드 세션이나 터미널·VS Code 확장에서 시작한 세션은 보여주지 않는다.
(출처: https://code.claude.com/docs/en/desktop)

Projects(베타)의 공식 문서에서 확인되는 검토 관련 기능은 모두 "스레드 하나(=PR 하나)" 단위다. **Overview** 탭이 어떤 PR이 리뷰 대기 중인지 보여주고, 카드에 Resolve conflicts / Fix CI / Address comments / Merge it / Review PR 같은 개별 스레드용 버튼이 있을 뿐, 여러 스레드의 PR을 하나로 합쳐 교차 검토하거나 통합 영향을 점검하는 기능은 문서에서 찾지 못했다. 별도 기능인 Code Review(연구 프리뷰, Team/Enterprise 전용)도 PR 하나의 diff를 여러 에이전트가 분석하는 것으로, 다른 PR·다른 세션과의 통합 검토는 다루지 않는다.
(출처: https://code.claude.com/docs/en/claude-projects , https://code.claude.com/docs/en/code-review)

실제로 Projects(베타)를 사용하는 과정에서 아래 5가지 문제를 반복적으로 경험했다.

## 문제 1: 프로젝트 대화가 로컬에 저장되지 않고 클라우드에만 존재한다
사용해 본 바로는 프로젝트 안의 대화 스레드가 내 컴퓨터(로컬)에 남지 않고 클라우드에서만 볼 수 있었다(로컬 저장·내보내기 기능은 공식 문서에서 찾지 못했다). 오프라인 백업, 개인 아카이브, 버전 관리(git 등)로의 편입이 어렵고, 클라우드 서비스 장애나 계정 문제 발생 시 대화 기록에 접근하지 못할 위험이 있다.

**제안**
- 프로젝트 단위로 대화 스레드를 로컬 폴더에 내보내는 "내보내기" 버튼 제공 (Markdown/JSON 등 구조화된 형식)
- 선택적으로, 지정한 로컬 폴더와 자동 동기화(백그라운드 백업)하는 옵션 제공
- 내보낸 파일에는 대화 시각, 참여자, 프로젝트명 메타데이터 포함

## 문제 2: 대화마다 '컴퓨터 사용'을 매번 다시 켜야 한다
컴퓨터 사용 기능은 데스크톱 앱 설정에서 켜지만, 우리가 쓸 때는 새 대화(세션)를 시작할 때마다 다시 활성화/승인해야 해서 반복 작업이 불편했다(공식 문서에서 확인된 것은 앱별·세션별 승인 방식까지다).

**제안**
- 프로젝트 단위로 "컴퓨터 사용 기본 허용" 같은 기본 권한 설정을 저장할 수 있게 한다
- 해당 프로젝트에서 시작하는 새 대화는 저장된 기본값을 자동 적용하고, 필요시 프로젝트 설정에서 언제든 껐다 켤 수 있게 한다
- 보안을 위해 프로젝트별 기본 허용 앱 목록을 명시적으로 관리하는 화면을 함께 제공한다

## 문제 3: 작업 도중 사용량(세션) 한도에 걸려 멈춘다
남은 사용량을 미리 가늠하기 어려워, 한창 작업 중에 갑자기 한도에 도달해 작업이 끊기는 경험을 했다. 공식 문서에 따르면 한도에 걸린 스레드는 리셋 후 자동으로 이어서 진행되지만(루틴이 시작한 스레드는 제외), 그 사이 흐름이 끊기고 언제 재개될지 예측하기 어렵다. 정확한 한도 수치와 세션 안에서 남은 양을 확인하는 방법은 문서에서 찾지 못했다.

**제안**
- 대화 화면에 남은 세션 한도를 실시간으로 보여주는 게이지(퍼센트 또는 남은 시간/횟수)를 추가한다
- 한도 임박(예: 10~20% 남음) 시 현재까지의 작업 상태를 자동으로 요약해 저장하고, 한도 리셋 후 이어서 작업할 수 있는 "인계 요약"을 제공한다
- 프로젝트 단위로 누적 사용량을 확인할 수 있는 대시보드를 제공해, 어떤 프로젝트가 한도를 많이 소모하는지 파악할 수 있게 한다

## 문제 4: 로컬에 설정해 둔 환경(스킬·전역 지침·MCP·훅·로그인된 도구)이 클라우드 세션으로 이어지지 않는다
로컬에서 구성한 스킬, 전역 지침(CLAUDE.md), 로컬 MCP 서버, 훅, 로그인된 도구가 클라우드 세션으로 넘어가지 않는다. 클라우드↔로컬을 오가는 것도 실시간 연결이 아니라 파일·브랜치·대화 요약을 옮기는 일회성 이관이다. 실제로 로컬 데스크톱 앱(Local 모드)에서는 클라우드 세션 목록이나 기록이 보이지 않아, 클라우드에서 하던 작업을 로컬에서 이어가려면 인계 메모를 사용자가 직접 복사해 붙여넣어야 했다.

**제안**
- 로컬 환경 프로필(사용 중인 스킬 목록, 전역 지침, MCP 서버 목록)을 클라우드 세션에 동기화하는 옵션 제공(민감 정보는 제외하고 선택적으로 공유)
- 클라우드 세션과 로컬 세션을 "같은 대화"로 이어주는 연결 기능 제공 — 대화 내용, 메모리, 관련 설정을 자동으로 인계
- 로컬 데스크톱 앱에서도 클라우드 세션 목록과 기록을 조회할 수 있게 하여, 로컬/클라우드를 오갈 때 사용자가 수동으로 메모를 옮기지 않아도 되게 한다

## 문제 5: 스레드끼리 서로 검토하지 않고, 하위 에이전트 보고를 메인이 검증하지 못한다
클라우드 세션(스레드)들이 각자 맡은 부분만 작업해 main에 PR을 내는데, 자기 범위 밖(다른 스레드가 바꾼 부분이나 통합 영향)에 대한 검토가 전혀 이루어지지 않는다. 로컬에서 하위 에이전트를 두어도 메인 에이전트가 이들을 관리·검증하는 능력이 아직 부족하다. 실제로 이번 작업에서 하위 에이전트가 트윗을 "280자 이내"라고 보고했지만 실제로는 초과였고, 한 번은 아무 보고 없이 종료해 메인이 직접 재검증해야 했다.

**제안**
- 프로젝트 단위 통합 리뷰어: 여러 스레드가 낸 PR을 모아 교차 검토(서로 다른 스레드가 같은 파일·인터페이스를 다르게 바꾸지 않았는지 등)
- PR을 병합하기 전에 다른 스레드의 최근 변경과 충돌·영향이 없는지 자동으로 점검하는 단계 추가
- 하위 에이전트(서브에이전트)의 보고를 메인이 자동으로 검증하는 체크: 주장(예: "280자 이내")과 실제 산출물(실제 글자 수)을 코드로 대조하고, 보고 없이 종료된 경우를 감지해 메인에게 알림

## 기대 효과
- 로컬 저장/동기화: 데이터 이중화, 오프라인 접근성, 개인 아카이빙 및 버전관리 친화성 향상
- 프로젝트 단위 권한: 반복 설정 피로 감소, 프로젝트별 보안 정책 관리 용이
- 한도 게이지 + 인계 요약: 작업 중단으로 인한 컨텍스트 손실 방지, 사용자 예측 가능성 향상
- 로컬 환경 동기화 + 세션 조회: 로컬↔클라우드 전환 시 반복 설정·수동 인계 부담 감소, 두 환경에서 같은 맥락을 유지
- 통합 리뷰어 + 보고 자동 검증: 여러 스레드/서브에이전트 결과물의 불일치·누락을 조기에 발견, 사용자가 직접 재검증하는 부담 감소

## 대안 검토
- (문제 1) 대안: 서드파티 브라우저 확장/스크립트로 대화를 스크래핑해 로컬 저장 — 유지보수 부담과 이용약관 위반 소지가 있어 공식 기능 제공이 더 바람직함
- (문제 2) 대안: 사용자가 매번 수동으로 토글 — 현재 방식이며 반복 피로가 큼. 전역(계정 전체) 기본값도 고려할 수 있으나, 앱마다 권한 범위가 다른 프로젝트 특성상 프로젝트 단위가 더 안전하고 유연함
- (문제 3) 대안: 한도 도달 후 안내 메시지만 강화 — 사후 안내로는 진행 중이던 작업 손실을 막지 못하므로, 사전 게이지 + 자동 요약이 더 근본적인 해결책
- (문제 4) 대안: 사용자가 매번 수동으로 인계 메모를 작성해 붙여넣기 — 현재 방식이며 반복 작업이 번거롭고 누락 위험이 있음. 저장소에 커밋하는 방식(`.claude/` 하위 파일)도 있으나 개인 전역 설정(사용자 스킬·CLAUDE.md 등)까지는 다루지 못하므로, 별도의 동기화/조회 기능이 더 근본적인 해결책
- (문제 5) 대안: 사용자가 매번 다른 스레드의 diff를 직접 훑어보고 통합 영향을 확인 — 스레드 수가 늘어날수록 비현실적임. 하위 에이전트의 보고를 그대로 신뢰하는 현재 방식도 이번처럼 오보고를 걸러내지 못하므로, 자동 교차 검토·보고 검증이 더 근본적인 해결책

---

## Summary (English)

**Target feature (re-confirmed)**: This proposal is about the new **"Projects" public beta** in the Claude desktop app's Code tab / claude.ai/code — not the older claude.ai chat Projects (knowledge files + instructions). It's "one ongoing conversation where Claude coordinates a stream of related work," splitting it into threads that are usually cloud sessions sharing repositories, instructions, and memory; each thread works on its own branch and opens a PR when needed. It's in public beta, rolling out gradually on Pro/Max (not yet on Team/Enterprise). (Source: https://code.claude.com/docs/en/claude-projects)

**Background**: Computer use is enabled in desktop settings and approved per session; session-based usage limits reset every 5 hours (Pro/Max), per official Claude Help Center articles. Cloud sessions start from a fresh repo clone and don't inherit anything installed/configured only on the local machine. Official docs describe review/merge actions (Resolve conflicts, Fix CI, Merge it, Review PR) as per-thread/per-PR controls in the Overview pane; no cross-thread integration review is described. The separate Code Review feature (research preview, Team/Enterprise only) also analyzes one PR's diff at a time. (Sources: support.claude.com usage-limits article; code.claude.com cloud-environments, claude-projects, code-review docs)

**Problem 1**: Project conversation threads are stored only in the cloud, not locally, limiting offline access, personal backups, and version control.
**Proposal**: Per-project export to local files (Markdown/JSON with metadata), plus an optional background sync to a chosen local folder.

**Problem 2**: "Computer use" must be re-enabled for every new conversation.
**Proposal**: A project-level default permission setting so new conversations in that project inherit the chosen computer-use default, with an explicit per-project allowed-app management screen.

**Problem 3**: Users hit the session usage limit mid-task with no warning, losing work-in-progress.
**Proposal**: A real-time usage gauge in the chat UI, an automatic work-state summary saved when the limit is nearly reached, and a per-project usage dashboard.

**Problem 4**: A locally configured environment (skills, global `CLAUDE.md` instructions, local MCP servers, hooks, logged-in tools) doesn't carry over to cloud sessions. Per official docs, cloud sessions start from a fresh repo clone, so anything installed/configured only on the local machine isn't available there; moving between cloud and local (teleport, or the desktop app's "Continue in") pushes files/branch/a conversation summary rather than maintaining a live link; and the local desktop app's session list only shows sessions it ran itself (local/SSH/WSL), not cloud sessions. In practice, this meant manually copy-pasting a handoff note to continue cloud work locally.
**Proposal**: An option to sync a "local environment profile" (skills, instructions, MCP server list) to cloud sessions; a connector that treats a cloud and local session as the same conversation, handing off context, memory, and settings; and a way to view the cloud session list/history from the local app.

**Problem 5**: Cloud session threads each work on their own scope and open a PR to main, but nothing reviews the integration impact outside a thread's own scope — no official cross-thread review was found. Locally, subagents report back to the main agent, but the main agent still can't reliably verify those reports: in this very task, a subagent reported a tweet was "under 280 characters" when it wasn't, and once finished without reporting at all, requiring the main agent to re-verify everything by hand.
**Proposal**: A project-level integrated reviewer that cross-checks PRs from multiple threads together; an automatic check for conflicts/impact against other threads' recent changes before merging; and an automated check that compares a subagent's claims against its actual output (and flags silent completions without a report).

**Expected impact**: better data resilience and offline/versioning support; less repetitive permission friction with safer per-project security control; reduced context loss and more predictable sessions around usage limits; less manual re-setup and copy-pasting when moving between local and cloud work; earlier detection of inconsistent or missing results across threads/subagents, reducing the burden of manual re-verification.

**Alternatives considered**: third-party scraping for local export (maintenance/ToS risk) vs. official export/sync; manual per-conversation toggling vs. project-level default; post-hoc limit notices vs. proactive gauge + handoff summary; manually written handoff notes vs. a built-in environment-profile sync and cross-surface session view; manually reading every thread's diff vs. automated cross-thread review and report verification — in each case the proposed approach is more robust than the alternative.
