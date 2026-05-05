# Consensus — Project Memory

## IdeaFlow 현재 프로젝트 — 20260501-1621

| 항목 | 내용 |
|------|------|
| 목표 | product-ready freemium 주식 스크리너, 웹 먼저 배포 |
| 현재 단계 | Phase 6 완료 (QA 리포트: .gstack/qa-reports/2026-05-02-production-qa.md) |
| Seed 전체 | .omx/seeds/20260501-1621-seed.yaml |
| 플랜 (생성 후) | .omx/plans/20260501-1621-plan.md |

### 핵심 결정
- **전략**: CANSLIM (핵심) + Piotroski + Magic Formula (Minervini 대체, KR은 OpenDART 파싱)
- **차별화**: US+KR 동시 + 구루 기준 투명 공개 (vs AlphaSquare = KR 전용, 블랙박스)
- **Auth**: /rankings 공개, 종목 상세(/app/instruments) 로그인 필요
- **플랫폼**: 웹 먼저 완성 → 모바일
- **수익모델**: freemium — 랭킹 무료, 상세 로그인, 전략 검증 후 유료 전환
- **폰트**: Public Sans 유지 (가장 가벼움, 교체 불필요)
- **Redis**: 현재 in-memory 유지, 트래픽 증가 시 추가

### 핵심 기술 과제
1. 데이터 로딩 18초+ → 3초 이하로 전면 구조 개선 (최우선)
2. 3전략 기준 실데이터 계산 완성
3. 프로토타입 수준 디자인 구현

### Phase 6 QA 결과 (2026-05-02)
- ISSUE-001 (Critical): /rankings → auth redirect — **FIXED** `8eef436`
- ISSUE-002 (Medium): Clerk dev keys in production — **DEFERRED** (Clerk dashboard 수동 작업 필요)
- ISSUE-003 (Low): US score_date stale Apr 25 — **AUTO-RESOLVES** 오늘 자정 UTC
- ISSUE-004 (Low): magic_formula_scored 0 — **AUTO-RESOLVES** nightly beat ebit 백필 후
- 헬스 스코어: **76 / 100** (론칭 가능)

### 다음 단계 (Phase 7 배포)
- [ ] Vercel에서 ISSUE-001 fix 배포 확인
- [ ] Clerk production keys 교체 (ISSUE-002)
- [ ] /ship 실행

### 완료 조건
- AC-01: 랭킹 첫 화면 3초 이내 로드
- AC-02: 3전략 모든 기준 실계산
- AC-03: 프로토타입 디자인 픽셀 수준 구현
- AC-04: US + KR 양쪽 지원
- AC-05: 소셜 로그인 포함 인증 완성
- AC-06: 초보 친화 UX (구루 기준 설명 포함)
- AC-07: Vercel 실배포
