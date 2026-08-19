FROM nginx:1.27-alpine

# Copia todas as páginas HTML da raiz do frontend automaticamente, em vez
# de listar cada arquivo (lista explícita já causou 404 em produção
# quando novas páginas - ex.: pecas.html, destinatarios.html - foram
# adicionadas ao projeto sem atualizar este Dockerfile).
COPY *.html /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/

# home.html (não index.html) é a página pública padrão de "/" - ver
# nginx.conf.
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80