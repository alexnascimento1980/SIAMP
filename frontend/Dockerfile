FROM nginx:1.27-alpine

# Copia todas as páginas HTML da raiz do frontend automaticamente, em vez
# de listar cada arquivo (lista explícita já causou 404 em produção
# quando novas páginas - ex.: pecas.html, destinatarios.html - foram
# adicionadas ao projeto sem atualizar este Dockerfile).
COPY *.html /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/

EXPOSE 80