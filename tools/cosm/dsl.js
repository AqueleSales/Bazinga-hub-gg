'use strict';
/* A linguagem dos temas: tudo o que um arquivo de tools/cosm/temas/*.js precisa. */
const B = require('./base');
const { M, N, Pl, F, P } = require('./kit');
const { EA, EP, fase } = require('./efeitos_kit');
const X = require('./extras_kit');
const I = require('./icones');
require('./icones_extra');            // registra os ícones extras (runas, armas, tecnologia...) em I.ICONES
const CATEGORIAS = ['anime', 'jogos', 'quadrinhos', 'esporte', 'fofo', 'sombrio', 'cotidiano', 'fantasia', 'basico', 'sazonal'];

/** especificação de um tema (só valida e guarda) */
function tema(s) {
    for (const k of ['id', 'pre', 'nome', 'cat', 'cor', 'cores', 'icone', 'lema', 'desc', 'itens']) if (s[k] === undefined) throw new Error(`tema ${s.id}: falta "${k}"`);
    if (!B.idOk(s.id)) throw new Error(`tema "${s.id}": id inválido (só a-z e _, até 24)`);
    if (!/^[a-z]{2,6}$/.test(s.pre)) throw new Error(`tema ${s.id}: o prefixo "pre" precisa ter de 2 a 6 letras minúsculas`);
    if (!CATEGORIAS.includes(s.cat)) throw new Error(`tema ${s.id}: categoria "${s.cat}" desconhecida`);
    return s;
}

module.exports = { tema, CATEGORIAS, B, P, I, M, N, Pl, F, EA, EP, fase, ...X };
