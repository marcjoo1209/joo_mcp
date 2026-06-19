"""애플리케이션 루트 패키지.

레이어드 아키텍처(위 → 아래로만 의존):
    api(routes) → services → repositories → db
가로지르는 공통: core(설정/예외), models(도메인), schemas(DTO)
"""
