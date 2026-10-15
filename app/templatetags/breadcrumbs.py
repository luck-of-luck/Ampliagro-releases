from django import template

register = template.Library()


@register.inclusion_tag("partials/breadcrumb.html")
def breadcrumb(*items):
    """
    Uso no template:
    {% load breadcrumbs %}
    {% breadcrumb "Início" "/" "Cadastros" "/cadastros/" "Funcionários" %}

    Os argumentos devem ser passados em pares: Nome, URL. O último argumento pode ser só o nome (página atual).
    """
    breadcrumbs_list = []

    # Processa de 2 em 2 (nome, url)
    i = 0
    while i < len(items):
        name = items[i]

        # Se houver um próximo item que comece com '/', ou se for string e não for o último, consideramos como URL
        # O Django passa args sequencialmente. Vamos assumir (Nome, Url, Nome, Url, NomeAtivo)
        if (
            i + 1 < len(items)
            and isinstance(items[i + 1], str)
            and items[i + 1].startswith("/")
        ):
            url = items[i + 1]
            breadcrumbs_list.append({"name": name, "url": url, "active": False})
            i += 2
        else:
            # É o último item (ativo)
            breadcrumbs_list.append({"name": name, "url": "", "active": True})
            i += 1

    return {"breadcrumbs": breadcrumbs_list}
