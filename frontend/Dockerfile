FROM nginx:1.27-alpine

# Copia todas as páginas HTML da raiz do frontend automaticamente, em vez
# de listar cada arquivo (lista explícita já causou 404 em produção
# quando novas páginas - ex.: pecas.html, destinatarios.html - foram
# adicionadas ao projeto sem atualizar este Dockerfile).
COPY *.html /usr/share/nginx/html/
COPY css/ /usr/share/nginx/html/css/
COPY js/ /usr/share/nginx/html/js/
COPY img/ /usr/share/nginx/html/img/
COPY favicon-16.png favicon-32.png apple-touch-icon.png /usr/share/nginx/html/

# nginx.conf.template fica em /etc/nginx/templates/ - a imagem oficial do
# nginx roda envsubst nele automaticamente na inicialização do container,
# gerando /etc/nginx/conf.d/default.conf. NGINX_ENVSUBST_FILTER restringe
# a substituição só a BACKEND_INTERNAL_URL, para não corromper as
# variáveis do próprio nginx no arquivo (ex.: $host, $uri) - sem o
# filtro, o envsubst tentaria substituir todo "$algumacoisa" que
# encontrasse, inclusive essas.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
ENV NGINX_ENVSUBST_FILTER=BACKEND_INTERNAL_URL

EXPOSE 80