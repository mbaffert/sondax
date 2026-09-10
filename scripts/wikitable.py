"""Lecture générique des tableaux wikitexte en grille.

Chaque tableau devient une liste de lignes ; chaque ligne une liste de cellules
dépliées (rowspan/colspan). Une cellule dépliée garde une référence à sa cellule
d'origine, pour distinguer « même valeur répétée par rowspan » de « valeur saisie ».
"""
import re


def split_top(s, sep):
    """Découpe s sur sep, hors [[ ]] et {{ }}."""
    out, depth, i, last = [], 0, 0, 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ('[[', '{{'):
            depth += 1; i += 2; continue
        if two in (']]', '}}'):
            depth = max(0, depth - 1); i += 2; continue
        if depth == 0 and s.startswith(sep, i):
            out.append(s[last:i]); i += len(sep); last = i; continue
        i += 1
    out.append(s[last:])
    return out


def split_attrs(cell):
    """'style=".." | contenu' -> (attrs, contenu). Premier '|' de niveau 0."""
    parts = split_top(cell, '|')
    if len(parts) == 1:
        return '', parts[0]
    attrs = parts[0]
    # un vrai bloc d'attributs contient '=' ; sinon le '|' faisait partie du contenu
    if '=' not in attrs:
        return '', cell
    return attrs, '|'.join(parts[1:])


class Cell:
    __slots__ = ('content', 'attrs', 'header', 'rowspan', 'colspan', 'uid')

    def __init__(self, content, attrs, header, uid):
        self.content, self.attrs, self.header, self.uid = content, attrs, header, uid
        rs = re.search(r'rowspan\s*=\s*"?(\d+)', attrs)
        cs = re.search(r'colspan\s*=\s*"?(\d+)', attrs)
        self.rowspan = int(rs.group(1)) if rs else 1
        self.colspan = int(cs.group(1)) if cs else 1


def iter_tables(text):
    """Renvoie (position, wikitexte) de chaque tableau de premier niveau."""
    pos, out = 0, []
    lines = text.split('\n')
    depth, start, offset = 0, None, 0
    offs = []
    for l in lines:
        offs.append(offset); offset += len(l) + 1
    for i, l in enumerate(lines):
        s = l.lstrip()
        if s.startswith('{|'):
            if depth == 0:
                start = i
            depth += 1
        elif s.startswith('|}'):
            depth -= 1
            if depth == 0 and start is not None:
                out.append((offs[start], '\n'.join(lines[start:i + 1])))
                start = None
    return out


def parse_rows(table):
    """Wikitexte d'un tableau -> liste de lignes brutes (liste de Cell)."""
    rows, cur, uid = [], None, 0
    lines = table.split('\n')[1:]  # saute '{|'
    for raw in lines:
        l = raw.strip()
        if l.startswith('|}'):
            break
        if l.startswith('|+'):
            continue
        if l.startswith('|-'):
            cur = []; rows.append(cur); continue
        if cur is None:
            cur = []; rows.append(cur)
        if l.startswith('!') or l.startswith('|'):
            header = l.startswith('!')
            body = l[1:]
            pieces = split_top(body, '!!' if header else '||')
            if header and len(pieces) == 1:
                pieces = split_top(body, '||')
            for p in pieces:
                attrs, content = split_attrs(p)
                uid += 1
                cur.append(Cell(content.strip(), attrs, header, uid))
        elif cur:
            # ligne de continuation de la cellule précédente
            cur[-1].content += '\n' + raw
    return [r for r in rows if r]


def to_grid(rows):
    """Déplie rowspan/colspan. Renvoie une liste de lignes de Cell (mêmes objets
    répétés sur les positions couvertes)."""
    grid, pending = [], {}  # pending[(r, c)] = Cell
    for r, row in enumerate(rows):
        line, c = [], 0
        cells = list(row)
        while cells or (r, c) in pending:
            if (r, c) in pending:
                line.append(pending.pop((r, c))); c += 1; continue
            cell = cells.pop(0)
            for dc in range(cell.colspan):
                line.append(cell)
                for dr in range(1, cell.rowspan):
                    pending[(r + dr, c + dc)] = cell
                c += 1
        grid.append(line)
    # lignes fantômes générées par un rowspan qui dépasse
    return grid
