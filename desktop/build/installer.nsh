; Personalização do instalador (o electron-builder inclui este arquivo sozinho: build/installer.nsh).
;
; Por que existe: ao ATUALIZAR de uma versão que tinha outro nome (Panteão -> Pantheon), o instalador renomeia os atalhos e logo em seguida manda
; abrir o app pelo ATALHO (--force-run, o que o "Procurar atualizações" usa). Na prática o Windows respondia "não pode encontrar ...\Pantheon.lnk",
; o app não reabria e a pessoa via uma janela de erro. Aqui o app é aberto pelo próprio .exe (não depende do atalho) e o atalho do Menu Iniciar
; é recriado se, por qualquer motivo, não existir.
!macro customInstall
  ${ifNot} ${FileExists} "$newStartMenuLink"
    CreateShortCut "$newStartMenuLink" "$appExe" "" "$appExe" 0 "" "" "${APP_DESCRIPTION}"
    ClearErrors
    WinShell::SetLnkAUMI "$newStartMenuLink" "${APP_ID}"
  ${endIf}
  StrCpy $launchLink "$appExe"
!macroend
