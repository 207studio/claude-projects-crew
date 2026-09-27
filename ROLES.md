# Roles — one page

| | project-handoff | portable-env | integration-review |
|---|---|---|---|
| **Role** | Memory in the repo | Moves setup to the cloud | Checks the whole, not one PR |
| **When** | Thread start · milestones · before stopping · limit near | Setting up a repo for Projects · "cloud doesn't know X" | Before opening/merging a PR · when a worker says "done" |
| **Input** | `HANDOFF.md`, `handoff/sessions/`, git state | `~/.claude`, `~/.claude.json`, repo `.claude/`, `.mcp.json` | base branch, other pushed branches/PRs, worker's claims block |
| **Output** | Committed note: summary · done · next · decisions · blockers · needs-local | Report: what won't travel, portability problems; copies into `.claude/` | Overlaps · predicted conflicts · drift · blast radius · dangling refs; PASS/FAIL per claim |
| **Problems** | 1 · 3 · 4 (mitigates) | 4 (solves for skills/agents/CLAUDE.md) · 2 (mitigates) | 5 |
| **Can't** | Save transcripts · see remaining usage | Turn on computer use · install plugins in cloud | Merge for you · replace tests |

## 한 장 요약

| | project-handoff | portable-env | integration-review |
|---|---|---|---|
| **역할** | 저장소에 남기는 기억 | 로컬 설정을 클라우드로 | PR 하나가 아니라 전체를 검토 |
| **언제** | 스레드 시작 · 중간 지점 · 종료 전 · 한도 임박 | Projects용 저장소 준비 · "클라우드가 X를 모름" | PR 열기/병합 전 · 하위 작업자가 "완료" 보고 시 |
| **입력** | `HANDOFF.md`, `handoff/sessions/`, git 상태 | `~/.claude`, `~/.claude.json`, 저장소 `.claude/`, `.mcp.json` | 기준 브랜치, push된 다른 브랜치·PR, 작업자의 claims 블록 |
| **출력** | 커밋된 인계 노트: 요약·완료·다음·결정·막힘·로컬 필요 | 안 넘어가는 항목·이식성 문제 보고, `.claude/`로 복사 | 겹침·충돌 예측·main 변화·영향 큰 파일·끊긴 참조, 주장별 PASS/FAIL |
| **문제** | 1·3·4 (완화) | 4 (스킬·에이전트·CLAUDE.md는 해결) · 2 (완화) | 5 |
| **못 하는 것** | 대화 원문 저장 · 남은 사용량 확인 | 컴퓨터 사용 켜기 · 클라우드에 플러그인 설치 | 대신 병합 · 테스트 대체 |
