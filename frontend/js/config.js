// Caminho relativo, não host absoluto: o nginx do frontend repassa
// tudo que cai em /api/ para o backend (ver nginx.conf.template) -
// tanto em desenvolvimento (docker compose) quanto em produção
// (Render). Front e backend são sempre a mesma origem para o
// navegador, o que evita problemas de cookie cross-site (ver
// nginx.conf.template para o porquê disso importar).
window.SIAMP_API_BASE_URL = "/api/v1";
