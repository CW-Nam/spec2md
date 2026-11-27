# 기능 영역 분류 (주제 id 참고)

여러 규격에서 같은 개념에 같은 주제 id를 쓰기 위한 참고 분류다. 이전 프로젝트(nr-3gpp-wiki)가 TS 38.300 V19.4.0 목차를 뼈대로 만든 기능 영역 57개(W01~W22, W23-01~35)를 옮겼다. id는 `raw/38300-j40/topics/topics.json`에서 쓰는 이름과 같다.

## 쓰는 방법

- 주제 범위가 아래 영역 하나와 같으면 그 영역의 id를 그대로 쓴다. 예: TS 38.321의 랜덤 액세스와 timing advance 조항 → `random-access-and-timing-advance`.
- 영역보다 좁은 주제는 새 id를 만든다. 같은 규격에 그 영역 id의 주제가 있으면 `related`로 연결한다.
- 분류에 없는 개념(예: positioning)은 새 id를 만든다. 이 분류는 빠짐없는 목록이 아니다.
- 이미 있는 `topics.json`의 id는 이 분류에 맞추려고 바꾸지 않는다(위키 링크 보호). 새로 쓰는 규격과 새 주제에만 적용한다.
- 관련 TS는 이전 프로젝트가 기록한 규격이다. 조항 수준의 대응은 아니다. `—`는 기록이 없다는 뜻이다.

## 기본 영역 (W01~W22)

| 이전 ID | id | 범위 | TS 38.300 | 관련 TS |
| --- | --- | --- | --- | --- |
| W01 | `overall-architecture-and-interfaces` | NG-RAN 구조, 기능 분담, NG/Xn, 무선 프로토콜 구조, AS/NAS 경계 | §4.1~4.4, §7.6 | — |
| W02 | `random-access-and-timing-advance` | 초기 접근 trigger, 4-step/2-step RA, timing advance | §9.2.6, §9.2.9 | 38.331, 38.321, 38.213 |
| W03 | `rrc-services-and-states` | RRC 기능, RRC_IDLE/INACTIVE/CONNECTED 상태, RRC 메시지 분할 | §7.1, §7.2, §7.10 | 38.331 |
| W03-01 | `identities` | UE·네트워크 식별자, I-RNTI | §8.1~8.3, Annex C, F | 38.331 |
| W04 | `physical-layer` | waveform·numerology, DL/UL 채널·신호, 물리 계층 절차, shared spectrum | §5.1~5.3, §5.5, §5.6, Annex B.2, B.3 | 38.211~38.215 |
| W05 | `system-information-and-access-control` | SI 방송·스케줄링·변경, 접근 제어 | §7.3, §7.4 | 38.304, 38.331 |
| W06 | `ue-capabilities` | capability 조회·보고, UE assistance information | §7.5, §7.9, §14 | 38.306, 38.331 |
| W07 | `carrier-aggregation-and-bandwidth-adaptation` | CA, SUL, BWP, SCell/BWP 활성·비활성 | §5.4, §6.7, §6.9, §6.10, §7.7, §7.8, §10.6, Annex B.1 | 38.331, 38.321, 38.213, 38.214 |
| W08 | `scheduling` | 스케줄러 동작, DL/UL 스케줄링, SR·BSR, rate control | §10 (§10.6, §10.9 제외) | 38.321, 38.213, 38.214 |
| W09 | `harq` | HARQ 동작·재전송 | §6.2.4 | 38.321, 38.212, 38.213, 38.214 |
| W10 | `ue-power-saving` | DRX, 절전 기능 | §11 | 38.321, 38.331 |
| W11 | `rlc` | RLC 전송 모드, ARQ | §6.3 | 38.322 |
| W12 | `pdcp` | PDCP 기능, 재설정 | §6.4 | 38.323 |
| W13 | `qos` | SDAP, QoS flow, AS QoS 처리 | §6.5, §12, Annex A | 37.324 |
| W14 | `mobility-measurements` | 측정 설정·보고 | §9.2.4 | 38.331, 38.215, 38.133 |
| W15 | `mobility-overview-and-idle-inactive` | 이동성 개요, RRC_IDLE/INACTIVE 이동성(셀 선택·재선택), SPID 우선순위 | §9.1, §9.2.1, §9.2.2, §9.2.10, Annex D | 38.304, 38.331 |
| W15 | `connected-mobility-handover` | RRC_CONNECTED 이동성: handover, CHO, LTM, RACH-less HO, 이동 지연 | §9.2.3, Annex G | 38.331, 38.133 |
| W15-01 | `self-configuration-and-self-optimisation` | SON: 자동 구성, 에너지 절감, 자동 최적화 | §15 | — |
| W16 | `radio-link-failure-and-beam-failure` | RLF, beam failure 검출·복구 | §9.2.7, §9.2.8 | 38.331, 38.321 |
| W17 | `security` | AS/NAS 보안 | §13 | 33.501, 33.401, 24.501, 24.301, 38.331 |
| W18, W19 | `multi-radio-dual-connectivity` | EN-DC, NR-DC 등 MR-DC 구성과 역할 | §4.5, §6.8 | 37.340, 36 계열, 38.401, 38.423, 38.425 |
| W20 | `registration-management` | 5GMM 상태, 등록, 이동 관리 | — (§7.6은 전달 경계) | 24.501, 23.501, 23.502 |
| W21 | `pdu-session-management` | 5GSM, PDU session과 AS 데이터 경로 | — (§12, Annex A와 연결) | 24.501, 23.501, 23.502 |
| W22 | `eps-interworking` | EPS NAS, 5GS/EPS interworking, NR↔E-UTRA 이동 | §9.3 | 24.301, 24.501, 23.401, 23.501, 23.502, 37.340 |

TS 38.300에서는 §9.3과 §9.4를 `inter-rat-mobility-and-access-restrictions` 한 주제로 묶었다(아래 "38.300 적용" 참고). W09, W11, W12 범위는 38.300 안에서 조항이 너무 작아 `layer2-overview-and-sublayers`에 들어 있다. 이 id들은 38.321·38.322·38.323 같은 상세 규격에서 쓴다.

## 확장 영역 (W23-01~35)

| 이전 ID | id | TS 38.300 |
| --- | --- | --- |
| W23-01 | `ran-sharing` | §4.6, Annex E |
| W23-02 | `integrated-access-and-backhaul` | §4.7, §6.11, §10.9 |
| W23-03 | `network-controlled-repeaters` | §4.9 |
| W23-04, W23-05 | `nr-femto-nodes-and-wireless-access-backhaul` | §4.10, §4.11 |
| W23-06 | `urllc` | §16.1 |
| W23-07 | `ims-voice` | §16.2 |
| W23-08 | `network-slicing` | §16.3 |
| W23-09 | `public-warning-system` | §16.4 |
| W23-10 | `emergency-services` | §16.5 |
| W23-11, W23-12 | `non-public-networks` | §4.8, §16.6, §16.7 |
| W23-13, W23-22 | `time-sensitive-communications` | §16.8, §16.17 |
| W23-14 | `nr-sidelink-communication` | §5.7, §16.9 |
| W23-15 | `multicast-broadcast-services` | §16.10 |
| W23-16 | `minimization-of-service-interruption` | §16.11 |
| W23-17 | `sidelink-relay` | §16.12 |
| W23-18, W23-27 | `reduced-capability-devices` | §16.13, §16.22 |
| W23-19 | `non-terrestrial-networks` | §16.14, Annex B.4 |
| W23-20, W23-21 | `extended-reality-services` | §16.15, §16.16 |
| W23-23 | `aerial-ue-communication` | §16.18 |
| W23-24 | `air-to-ground-networks` | §16.19 |
| W23-25 | `ai-ml-for-ng-ran` | §16.20 |
| W23-26 | `multi-path-relay` | §16.21 |
| W23-28 | `ambient-iot` | §16.23 |
| W23-29 | `interference-management` | §17 |
| W23-30 | `small-data-transmission` | §18 |
| W23-31 | `nr-coverage-enhancements` | §19 |
| W23-32 | `multi-usim-devices` | §20.1, §20.3, §20.4 |
| W23-33 | `qoe-measurements` | §21 |
| W23-34 | `ai-ml-for-nr-air-interface` | §22 |
| W23-35 | `sbfd` | §23 |

이전 ID 두 개를 한 id로 합친 행은 38.300에서 조항이 작고 범위가 이어져 한 주제로 둔 것이다.

## 38.300 적용

분류 영역이 아니지만 38.300 주제로 쓰는 id: `layer2-overview-and-sublayers`(§6.1~6.4, §6.6, §6.12), `sidelink-identities`(§8.4), `paging`(§9.2.5, §20.2), `inter-rat-mobility-and-access-restrictions`(§9.3, §9.4).
