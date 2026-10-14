# Imagens de referência dos temas (pasta do dono)

Coloque aqui as imagens que servem de **referência de arte** pros temas de cosméticos (ver `docs/PLANO_TEMAS.md`, seção 6, e `docs/ARTE_TEMAS.md`).

**Por quê**: imagem colada no chat NÃO vira arquivo no disco, então eu não consigo decalcar dela. Salvando aqui, a próxima conversa lê o arquivo e traça o contorno igual ao original
(foi assim com as marcas do Sukuna). Desenhar de memória deu errado (o símbolo da aranha saiu um inseto).

**Como**: uma pasta por tema e nomes claros, por exemplo:

```
docs/refs/simbionte/simbolo.png      <- a aranha branca no fundo preto
docs/refs/aranha/emblemas.png        <- o gráfico "Spider-Man Symbol Evolution"
docs/refs/jojo/letras.png            <- print das letras "ゴゴゴ"
docs/refs/jojo/relogio.png
docs/refs/lol/hextech.png
```

Dicas: fundo liso, contraste alto, o maior tamanho que tiver (500 px ou mais), um símbolo por arquivo quando der.

Observações:
- Estas imagens são de terceiros, só pra decalcar localmente. Se o repositório um dia ficar público, **não** envie esta pasta (adicione `docs/refs/` ao `.gitignore`).
- Se a pasta for ao `.gitignore`, o `Glob` pode não enxergar os arquivos: liste com `ls docs/refs/*`.
