"""Internationalization (i18n) system for KARLOS ANNOTATOR.

Supports 5 languages: Español, English, Français, Português, 日本語.
Language preference persists via QSettings.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from karlos_core import catalogo, identidad


def idioma_del_sistema(local: str | None = None) -> str:
    """El idioma del sistema, si el programa lo habla; si no, inglés.

    ``local`` es el nombre que da el sistema («es_EC», «pt_PT»); por
    defecto, el de esta máquina.
    """
    if local is None:
        from PySide6.QtCore import QLocale
        local = QLocale.system().name()
    codigo = local.split("_")[0]
    return codigo if codigo in I18n.LANGS else "en"


class I18n(QObject):
    """Singleton-style internationalization manager.

    Usage:
        i18n = I18n()
        i18n.t("hub.load_folder")

    Signal:
        language_changed() — emitted when the user switches language.
            All views should reconnect their strings when this fires.
    """

    language_changed = Signal()

    LANGS: dict[str, str] = {
        "es": "Español",
        "en": "English",
        "fr": "Français",
        "pt": "Português",
        "it": "Italiano",
        "ja": "日本語",
    }

    LANG_FLAGS: dict[str, str] = {
        "es": "\U0001f1ea\U0001f1f8",
        "en": "\U0001f1ec\U0001f1e7",
        "fr": "\U0001f1eb\U0001f1f7",
        "pt": "\U0001f1e7\U0001f1f7",
        "it": "\U0001f1ee\U0001f1f9",
        "ja": "\U0001f1ef\U0001f1f5",
    }

    _instance: I18n | None = None

    def __new__(cls) -> I18n:
        if cls._instance is not None:
            return cls._instance
        obj = super().__new__(cls)
        cls._instance = obj
        return obj

    def __init__(self) -> None:
        if hasattr(self, '_lang'):
            return  # already initialized
        super().__init__()
        # Los ajustes de la edición en marcha (decisión 0006).
        self._settings = identidad.ajustes()
        # La primera vez, el del sistema: quien abre el programa por primera
        # vez lo lee ya en su idioma (decisión 0006, F5.3d).
        guardado = self._settings.value("i18n/language", "") or ""
        self._lang = guardado if guardado in self.LANGS else idioma_del_sistema()

    @property
    def lang(self) -> str:
        return self._lang

    @property
    def lang_name(self) -> str:
        return self.LANGS.get(self._lang, self._lang)

    def set_lang(self, code: str) -> None:
        """Switch language and persist preference."""
        if code not in self.LANGS:
            return
        if code == self._lang:
            return
        self._lang = code
        self._settings.setValue("i18n/language", code)
        self.language_changed.emit()

    def t(self, key: str, **kwargs: str) -> str:
        """Translate a key into the current language.

        Args:
            key: Dot-notation translation key (e.g. "hub.title").
            **kwargs: Optional format substitutions.

        Returns:
            Translated string, or the key itself if not found.

        Los textos del deporte que se anota van primero (decisión 0004):
        el árbol de preguntas del karate y su identidad son suyos.
        """
        entry = catalogo.activo().textos().get(key) or self._STRINGS.get(key)
        if entry is None:
            return key
        text = entry.get(self._lang) or entry.get("en") or key
        # Las teclas de las fases y la de retirar son del deporte (decisión
        # 0008): el karate tiene cuatro dígitos y Shift+1. Se ponen aquí y no
        # en cada llamada, que son una docena de avisos repartidos por el
        # programa.
        if "{teclas}" in text or "{retirar}" in text:
            from karlos_core.tiempo_movimiento import (resumen_de_teclas,
                                                       tecla_de_retirar)
            kwargs = {"teclas": resumen_de_teclas(),
                      "retirar": tecla_de_retirar(), **kwargs}
        if kwargs:
            text = text.format(**kwargs)
        return text

    # ──────────────────────────────────────────────────────────────
    # Translation dictionary
    # ──────────────────────────────────────────────────────────────
    _STRINGS: dict[str, dict[str, str]] = {
        # ── Los avisos del modo asistido ─────────────────────────────
        # Desde la 1.2 (19-10-2026) van en las seis lenguas. Un deporte puede
        # pisarlos en sus textos (decisión 0004).
        "pro.modo_asistido": {"es": "MODO ASISTIDO — {atleta}. {teclas}", "en": "ASSISTED MODE — {atleta}. {teclas}", "fr": "MODE ASSISTÉ — {atleta}. {teclas}", "pt": "MODO ASSISTIDO — {atleta}. {teclas}", "it": "MODALITÀ ASSISTITA — {atleta}. {teclas}", "ja": "アシストモード — {atleta}。{teclas}"},
        "pro.teclas_io": {"es": "[I] inicio · [O] fin · las preguntas se abren al marcar el inicio", "en": "[I] start · [O] end · the questions open when the start is marked", "fr": "[I] début · [O] fin · les questions s'ouvrent au marquage du début", "pt": "[I] início · [O] fim · as perguntas abrem-se ao marcar o início", "it": "[I] inizio · [O] fine · le domande si aprono al segnare l'inizio", "ja": "[I] 開始 · [O] 終了 · 開始を記録すると質問が開きます"},
        "pro.sin_inicio": {"es": "Ningún inicio marcado: use [I]", "en": "No start marked: use [I]", "fr": "Aucun début marqué : utilisez [I]", "pt": "Nenhum início marcado: use [I]", "it": "Nessun inizio segnato: usa [I]", "ja": "開始が未記録：[I] を使ってください"},
        "pro.ir_al_fin": {"es": "{tecnica} — vaya hasta el fin y pulse [O]", "en": "{tecnica} — go to the end and press [O]", "fr": "{tecnica} — allez à la fin et appuyez sur [O]", "pt": "{tecnica} — vá até o fim e pressione [O]", "it": "{tecnica} — vai alla fine e premi [O]", "ja": "{tecnica} — 終了位置へ進んで [O] を押してください"},
        "pro.anotada": {"es": "{tecnica} anotada — {pista}", "en": "{tecnica} recorded — {pista}", "fr": "{tecnica} enregistrée — {pista}", "pt": "{tecnica} anotada — {pista}", "it": "{tecnica} registrata — {pista}", "ja": "{tecnica} を記録 — {pista}"},
        "pro.pista_i": {"es": "[I] para la siguiente acción", "en": "[I] for the next action", "fr": "[I] pour l'action suivante", "pt": "[I] para a próxima ação", "it": "[I] per la prossima azione", "ja": "次のアクションは [I]"},
        "pro.cancelado": {"es": "Preguntas canceladas", "en": "Questions cancelled", "fr": "Questions annulées", "pt": "Percurso cancelado", "it": "Domande annullate", "ja": "質問を取り消しました"},
        "pro.descartada": {"es": "{descripcion}: descartada, sin fin", "en": "{descripcion}: discarded, without end", "fr": "{descripcion} : abandonnée, sans fin", "pt": "{descripcion}: descartada, sem fim", "it": "{descripcion}: scartata, senza fine", "ja": "{descripcion}：終了なしで破棄"},
        "pro.aviso_sin_fin": {"es": "A esta acción aún le falta el fin. Vaya hasta su fin y pulse [O]. Para descartarla, pulse [{tecla}] otra vez.", "en": "This action still has no end. Go to its end and press [O]. To discard it, press [{tecla}] again.", "fr": "Cette action n'a pas encore de fin. Allez à sa fin et appuyez sur [O]. Pour l'abandonner, appuyez de nouveau sur [{tecla}].", "pt": "Ainda falta o fim desta ação. Vá até o fim dela e pressione [O]. Para descartá-la, pressione [{tecla}] outra vez.", "it": "A questa azione manca ancora la fine. Vai alla sua fine e premi [O]. Per scartarla, premi di nuovo [{tecla}].", "ja": "このアクションにはまだ終了がありません。終了位置へ進んで [O] を押してください。破棄するにはもう一度 [{tecla}] を押します。"},
        "pro.pendiente_sin_fin": {"es": "⚠ {descripcion}: falta el fin [O]", "en": "⚠ {descripcion}: end missing [O]", "fr": "⚠ {descripcion} : fin manquante [O]", "pt": "⚠ {descripcion}: falta o fim [O]", "it": "⚠ {descripcion}: manca la fine [O]", "ja": "⚠ {descripcion}：終了が未記録 [O]"},
        "pro.estado_sin_fin": {"es": "{descripcion} aún no tiene fin — [O] en su fin, o [{tecla}] otra vez para descartarla", "en": "{descripcion} has no end yet — [O] at its end, or [{tecla}] again to discard it", "fr": "{descripcion} n'a pas encore de fin — [O] à sa fin, ou [{tecla}] de nouveau pour l'abandonner", "pt": "{descripcion} ainda não tem fim — [O] no fim dela, ou [{tecla}] outra vez para descartá-la", "it": "{descripcion} non ha ancora la fine — [O] alla sua fine, o [{tecla}] di nuovo per scartarla", "ja": "{descripcion} はまだ終了がありません — 終了位置で [O]、または [{tecla}] をもう一度押して破棄"},
        "pro.espera_titulo": {"es": "{atleta} · falta el fin{inicio}", "en": "{atleta} · end missing{inicio}", "fr": "{atleta} · fin manquante{inicio}", "pt": "{atleta} · falta o fim{inicio}", "it": "{atleta} · manca la fine{inicio}", "ja": "{atleta} · 終了が未記録{inicio}"},
        "pro.espera_desde": {"es": " desde f{frame}", "en": " from f{frame}", "fr": " depuis f{frame}", "pt": " desde f{frame}", "it": " da f{frame}", "ja": " f{frame} から"},
        "pro.espera_pista": {"es": "Vaya hasta el fin de la acción y pulse [O]", "en": "Go to the end of the action and press [O]", "fr": "Allez à la fin de l'action et appuyez sur [O]", "pt": "Vá até o fim da ação e pressione [O]", "it": "Vai alla fine dell'azione e premi [O]", "ja": "アクションの終了位置へ進んで [O] を押してください"},
        "pro.fin_antes_inicio": {"es": "El fin (f{fin}) tiene que ser posterior al inicio (f{inicio})", "en": "The end (f{fin}) must come after the start (f{inicio})", "fr": "La fin (f{fin}) doit être après le début (f{inicio})", "pt": "O fim (f{fin}) tem de ser posterior ao início (f{inicio})", "it": "La fine (f{fin}) deve venire dopo l'inizio (f{inicio})", "ja": "終了（f{fin}）は開始（f{inicio}）より後でなければなりません"},
        "pro.marque_inicio": {"es": "Marque primero el inicio con [I]", "en": "Mark the start first with [I]", "fr": "Marquez d'abord le début avec [I]", "pt": "Marque primeiro o início com [I]", "it": "Segna prima l'inizio con [I]", "ja": "まず [I] で開始を記録してください"},
        "pro.asalto_inicio": {"es": "Asalto {n} — inicio marcado. [G] marca el fin.  ·  {resumen}", "en": "Round {n} — start marked. [G] marks the end.  ·  {resumen}", "fr": "Round {n} — début marqué. [G] marque la fin.  ·  {resumen}", "pt": "Assalto {n} — início marcado. [G] marca o fim.  ·  {resumen}", "it": "Round {n} — inizio segnato. [G] segna la fine.  ·  {resumen}", "ja": "ラウンド {n} — 開始を記録。[G] で終了。 · {resumen}"},
        "pro.asalto_cerrado": {"es": "Asalto {n} cerrado. [F] marca el inicio del {siguiente}.  ·  {resumen}", "en": "Round {n} closed. [F] marks the start of round {siguiente}.  ·  {resumen}", "fr": "Round {n} fermé. [F] marque le début du round {siguiente}.  ·  {resumen}", "pt": "Assalto {n} fechado. [F] marca o início do {siguiente}.  ·  {resumen}", "it": "Round {n} chiuso. [F] segna l'inizio del round {siguiente}.  ·  {resumen}", "ja": "ラウンド {n} を終了。[F] でラウンド {siguiente} の開始。 · {resumen}"},
        "pro.asalto_sin_inicio": {"es": "El asalto {n} aún no tiene inicio: márquelo con [F].", "en": "Round {n} has no start yet: mark it with [F].", "fr": "Le round {n} n'a pas encore de début : marquez-le avec [F].", "pt": "O assalto {n} ainda não tem início: marque-o com [F].", "it": "Il round {n} non ha ancora l'inizio: segnalo con [F].", "ja": "ラウンド {n} の開始が未記録：[F] で記録してください。"},
        "pro.analisando_i": {"es": "Analizando: {target} — [I] marca el inicio de la acción", "en": "Analysing: {target} — [I] marks the start of the action", "fr": "Analyse : {target} — [I] marque le début de l'action", "pt": "Analisando: {target} — [I] marca o início da ação", "it": "Analisi: {target} — [I] segna l'inizio dell'azione", "ja": "分析中：{target} — [I] でアクションの開始"},
        "pro.fim_luta": {"es": "FIN del combate — frame {frame} ({dur})", "en": "END of the bout — frame {frame} ({dur})", "fr": "FIN du combat — image {frame} ({dur})", "pt": "FIM da luta — frame {frame} ({dur})", "it": "FINE dell'incontro — frame {frame} ({dur})", "ja": "試合終了 — フレーム {frame}（{dur}）"},
        "pro.analisando_f": {"es": "Analizando: {target} — pulse [F] para marcar el inicio", "en": "Analysing: {target} — press [F] to mark the start", "fr": "Analyse : {target} — appuyez sur [F] pour marquer le début", "pt": "Analisando: {target} — pressione [F] para marcar o início", "it": "Analisi: {target} — premi [F] per segnare l'inizio", "ja": "分析中：{target} — [F] で開始を記録"},
        "pro.luta_nova": {"es": "Combate nuevo — pulse [F] para marcar el inicio", "en": "New bout — press [F] to mark the start", "fr": "Nouveau combat — appuyez sur [F] pour marquer le début", "pt": "Luta nova — pressione [F] para marcar o início", "it": "Nuovo incontro — premi [F] per segnare l'inizio", "ja": "新しい試合 — [F] で開始を記録"},
        "pro.continue": {"es": "Siga anotando — pulse [F] para marcar el inicio", "en": "Keep annotating — press [F] to mark the start", "fr": "Continuez à annoter — appuyez sur [F] pour marquer le début", "pt": "Continue anotando — pressione [F] para marcar o início", "it": "Continua ad annotare — premi [F] per segnare l'inizio", "ja": "記録を続ける — [F] で開始を記録"},
        "pro.pronto": {"es": "Listo — elija una sesión o cargue una carpeta de vídeos.", "en": "Ready — choose a session or load a video folder.", "fr": "Prêt — choisissez une session ou chargez un dossier vidéo.", "pt": "Pronto — escolha uma sessão ou carregue uma pasta de vídeos.", "it": "Pronto — scegli una sessione o carica una cartella di video.", "ja": "準備完了 — セッションを選ぶか動画フォルダを読み込んでください。"},
        "pro.dados_atualizados": {"es": "Datos del combate actualizados.", "en": "Bout data updated.", "fr": "Données du combat mises à jour.", "pt": "Dados da luta atualizados.", "it": "Dati dell'incontro aggiornati.", "ja": "試合データを更新しました。"},
        "pro.sin_accion_puntuar": {"es": "No hay ninguna acción que puntuar", "en": "No action to score", "fr": "Aucune action à marquer", "pt": "Não há nenhuma ação para pontuar", "it": "Nessuna azione da segnare a punti", "ja": "得点にするアクションがありません"},
        "pro.no_puntua": {"es": "{tecnica} no es una técnica que puntúe", "en": "{tecnica} is not a scoring technique", "fr": "{tecnica} n'est pas une technique qui marque", "pt": "{tecnica} não é uma técnica que pontue", "it": "{tecnica} non è una tecnica che fa punti", "ja": "{tecnica} は得点技ではありません"},
        "pro.passe": {"es": "pasada {n}", "en": "pass {n}", "fr": "passe {n}", "pt": "passe {n}", "it": "passata {n}", "ja": "パス {n}"},
        "pro.passe_tooltip": {"es": "pasada {n} — {atleta}", "en": "pass {n} — {atleta}", "fr": "passe {n} — {atleta}", "pt": "passe {n} — {atleta}", "it": "passata {n} — {atleta}", "ja": "パス {n} — {atleta}"},
        "pro.inicio_combate": {"es": "inicio del combate — f{frame}", "en": "bout start — f{frame}", "fr": "début du combat — f{frame}", "pt": "início do combate — f{frame}", "it": "inizio dell'incontro — f{frame}", "ja": "試合開始 — f{frame}"},
        "pro.fim_combate": {"es": "fin del combate — f{frame}", "en": "bout end — f{frame}", "fr": "fin du combat — f{frame}", "pt": "fim do combate — f{frame}", "it": "fine dell'incontro — f{frame}", "ja": "試合終了 — f{frame}"},
        "pro.combate_tooltip": {"es": "combate f{inicio}–f{fim} · {dur} s", "en": "bout f{inicio}–f{fim} · {dur} s", "fr": "combat f{inicio}–f{fim} · {dur} s", "pt": "combate f{inicio}–f{fim} · {dur} s", "it": "incontro f{inicio}–f{fim} · {dur} s", "ja": "試合 f{inicio}–f{fim} · {dur} 秒"},
        "pro.sin_tecnica_anterior": {"es": "No hay técnica anterior que repetir.", "en": "No previous technique to repeat.", "fr": "Aucune technique précédente à répéter.", "pt": "Não há técnica anterior para repetir.", "it": "Nessuna tecnica precedente da ripetere.", "ja": "繰り返す前の技がありません。"},
        "pro.parada_cancelada": {"es": "Parada del árbitro cancelada.", "en": "Referee stop cancelled.", "fr": "Arrêt de l'arbitre annulé.", "pt": "Parada do árbitro cancelada.", "it": "Interruzione dell'arbitro annullata.", "ja": "主審の中断を取り消しました。"},
        "pro.parada_pendiente": {"es": "Parada del árbitro ({tipo}) [{atleta}] — pulse [O] para confirmar", "en": "Referee stop ({tipo}) [{atleta}] — press [O] to confirm", "fr": "Arrêt de l'arbitre ({tipo}) [{atleta}] — appuyez sur [O] pour confirmer", "pt": "Parada do árbitro ({tipo}) [{atleta}] — press [O] to confirm", "it": "Interruzione dell'arbitro ({tipo}) [{atleta}] — premi [O] per confermare", "ja": "主審の中断（{tipo}）[{atleta}] — [O] で確定"},
        "pro.agora": {"es": "Ahora {atleta} · {pista}", "en": "Now {atleta} · {pista}", "fr": "Maintenant {atleta} · {pista}", "pt": "Agora {atleta} · {pista}", "it": "Ora {atleta} · {pista}", "ja": "次は {atleta} · {pista}"},
        "pro.pista_marca_inicio": {"es": "[I] marca el inicio de la acción", "en": "[I] marks the start of the action", "fr": "[I] marque le début de l'action", "pt": "[I] marca o início da ação", "it": "[I] segna l'inizio dell'azione", "ja": "[I] でアクションの開始"},
        "pro.no_ident_titulo": {"es": "No identificable", "en": "Unidentifiable", "fr": "Non identifiable", "pt": "Não identificável", "it": "Non identificabile", "ja": "識別不能"},
        "pro.assistido": {"es": "ASISTIDO", "en": "ASSISTED", "fr": "ASSISTÉ", "pt": "ASSISTIDO", "it": "ASSISTITO", "ja": "アシスト"},
        "pro.em_curso": {"es": "… en curso", "en": "… in progress", "fr": "… en cours", "pt": "… em curso", "it": "… in corso", "ja": "… 進行中"},
        "pro.lema": {"es": "EL PROGRAMA MARCA · USTED DECIDE", "en": "THE PROGRAM MARKS · YOU DECIDE", "fr": "LE PROGRAMME MARQUE · VOUS DÉCIDEZ", "pt": "O PROGRAMA MARCA · VOCÊ DECIDE", "it": "IL PROGRAMMA SEGNA · TU DECIDI", "ja": "プログラムが記録し · あなたが判断する"},
        "pro.registro": {"es": "Registro", "en": "Log", "fr": "Registre", "pt": "Registro", "it": "Registro", "ja": "記録"},
        "pro.importar": {"es": "Importar", "en": "Import", "fr": "Importer", "pt": "Importar", "it": "Importa", "ja": "読み込み"},
        "pro.exportar": {"es": "Exportar", "en": "Export", "fr": "Exporter", "pt": "Exportar", "it": "Esporta", "ja": "書き出し"},
        "toolbar.analise": {"es": "Análisis…", "en": "Analysis…", "fr": "Analyse…", "pt": "Análise…", "it": "Analisi…", "ja": "分析…"},
        "pro.no_ident_pregunta": {"es": "¿Por qué no se puede identificar esta acción?", "en": "Why can't this action be identified?", "fr": "Pourquoi cette action ne peut-elle pas être identifiée ?", "pt": "Porque não se consegue identificar esta ação?", "it": "Perché questa azione non si può identificare?", "ja": "このアクションを識別できないのはなぜですか？"},

        # ── Avisos y diálogos que hasta la 1.2 iban escritos a mano en ──
        # portugués o español, ahora en las seis lenguas (19-10-2026).
        "stat.luta_ajustada": {"es": "Combate ajustado: f{inicio}–f{fim}", "en": "Bout adjusted: f{inicio}–f{fim}", "fr": "Combat ajusté : f{inicio}–f{fim}", "pt": "Luta ajustada: f{inicio}–f{fim}", "it": "Incontro regolato: f{inicio}–f{fim}", "ja": "試合を調整：f{inicio}–f{fim}"},
        "dialog.apagar_cola": {"es": "Los límites del combate no se tocan.\nQueda una copia en .karlos_sessions/backups.", "en": "The bout limits are not touched.\nA copy is kept in .karlos_sessions/backups.", "fr": "Les limites du combat ne sont pas touchées.\nUne copie reste dans .karlos_sessions/backups.", "pt": "Os limites do combate não se tocam.\nFica uma cópia em .karlos_sessions/backups.", "it": "I limiti dell'incontro non si toccano.\nResta una copia in .karlos_sessions/backups.", "ja": "試合の範囲は変更されません。\n.karlos_sessions/backups にコピーが残ります。"},
        "dialog.apagar_paradas_info": {"es": "{n} son paradas del árbitro.\n{cola}", "en": "{n} are referee stops.\n{cola}", "fr": "{n} sont des arrêts de l'arbitre.\n{cola}", "pt": "{n} são paradas do árbitro.\n{cola}", "it": "{n} sono interruzioni dell'arbitro.\n{cola}", "ja": "{n} 件は主審の中断です。\n{cola}"},
        "dialog.apagar_tudo": {"es": "Borrar todo", "en": "Delete all", "fr": "Tout effacer", "pt": "Apagar tudo", "it": "Cancella tutto", "ja": "すべて削除"},
        "dialog.manter_paradas": {"es": "Mantener las paradas", "en": "Keep the stops", "fr": "Garder les arrêts", "pt": "Manter as paradas", "it": "Mantieni le interruzioni", "ja": "中断を残す"},
        "dialog.cancelar": {"es": "Cancelar", "en": "Cancel", "fr": "Annuler", "pt": "Cancelar", "it": "Annulla", "ja": "キャンセル"},
        "stat.nada_que_apagar": {"es": "No hay anotaciones que borrar.", "en": "No annotations to delete.", "fr": "Aucune annotation à effacer.", "pt": "Não há anotações para apagar.", "it": "Nessuna annotazione da cancellare.", "ja": "削除する記録がありません。"},
        "dialog.apagar_titulo": {"es": "Borrar anotaciones", "en": "Delete annotations", "fr": "Effacer les annotations", "pt": "Apagar anotações", "it": "Cancella annotazioni", "ja": "記録を削除"},
        "dialog.apagar_pregunta_combate": {"es": "¿Borrar las {n} anotaciones de este combate?", "en": "Delete the {n} annotations of this bout?", "fr": "Effacer les {n} annotations de ce combat ?", "pt": "Apagar as {n} anotações deste combate?", "it": "Cancellare le {n} annotazioni di questo incontro?", "ja": "この試合の {n} 件の記録を削除しますか？"},
        "stat.apagadas": {"es": "{n} anotaciones borradas — [Ctrl+Z] deshace", "en": "{n} annotations deleted — [Ctrl+Z] undoes", "fr": "{n} annotations effacées — [Ctrl+Z] annule", "pt": "{n} anotações apagadas — [Ctrl+Z] desfaz", "it": "{n} annotazioni cancellate — [Ctrl+Z] annulla", "ja": "{n} 件の記録を削除 — [Ctrl+Z] で元に戻す"},
        "stat.paradas_mantidas": {"es": " ({n} paradas mantenidas)", "en": " ({n} stops kept)", "fr": " ({n} arrêts gardés)", "pt": " ({n} paradas mantidas)", "it": " ({n} interruzioni mantenute)", "ja": "（中断 {n} 件を保持）"},
        "pro.parada_arbitro": {"es": "Parada del árbitro", "en": "Referee stop", "fr": "Arrêt de l'arbitre", "pt": "Parada do árbitro", "it": "Interruzione dell'arbitro", "ja": "主審の中断"},
        "pro.acao": {"es": "Acción", "en": "Action", "fr": "Action", "pt": "Ação", "it": "Azione", "ja": "アクション"},
        "stat.dividir_tecnica": {"es": "Para dividir, elija primero la técnica de la acción en curso", "en": "To split, first choose the technique of the current action", "fr": "Pour diviser, choisissez d'abord la technique de l'action en cours", "pt": "Para dividir, escolha primeiro a técnica da ação em curso", "it": "Per dividere, scegli prima la tecnica dell'azione in corso", "ja": "分割するには、まず進行中のアクションの技を選んでください"},
        "stat.dividido": {"es": "Dividido en el frame {frame} — anote ahora la segunda acción", "en": "Split at frame {frame} — now annotate the second action", "fr": "Divisé à l'image {frame} — annotez maintenant la seconde action", "pt": "Dividido no frame {frame} — anote agora a segunda ação", "it": "Diviso al frame {frame} — annota ora la seconda azione", "ja": "フレーム {frame} で分割 — 2つ目のアクションを記録してください"},
        "stat.selecione_anotacao": {"es": "Seleccione primero una anotación en el registro", "en": "First select an annotation in the log", "fr": "Sélectionnez d'abord une annotation dans le registre", "pt": "Selecione primeiro uma anotação no registro", "it": "Seleziona prima un'annotazione nel registro", "ja": "まず記録から注釈を選んでください"},
        "stat.anotacao_fixada": {"es": "Anotación {n}: {etiqueta} fijado en el frame {frame} ({dur}s)", "en": "Annotation {n}: {etiqueta} set at frame {frame} ({dur}s)", "fr": "Annotation {n} : {etiqueta} fixé à l'image {frame} ({dur}s)", "pt": "Anotação {n}: {etiqueta} fixado no frame {frame} ({dur}s)", "it": "Annotazione {n}: {etiqueta} fissato al frame {frame} ({dur}s)", "ja": "注釈 {n}：{etiqueta} をフレーム {frame} に設定（{dur}s）"},
        "stat.etiqueta_inicio": {"es": "inicio", "en": "start", "fr": "début", "pt": "inicio", "it": "inizio", "ja": "開始"},
        "stat.etiqueta_fim": {"es": "fin", "en": "end", "fr": "fin", "pt": "fin", "it": "fine", "ja": "終了"},
        "stat.anotacao_atualizada": {"es": "Anotación {n} actualizada: {tecnica} [{atleta}]", "en": "Annotation {n} updated: {tecnica} [{atleta}]", "fr": "Annotation {n} mise à jour : {tecnica} [{atleta}]", "pt": "Anotação {n} atualizada: {tecnica} [{atleta}]", "it": "Annotazione {n} aggiornata: {tecnica} [{atleta}]", "ja": "注釈 {n} を更新：{tecnica} [{atleta}]"},
        "stat.abra_video": {"es": "Abra primero un vídeo", "en": "Open a video first", "fr": "Ouvrez d'abord une vidéo", "pt": "Abra primeiro um vídeo", "it": "Apri prima un video", "ja": "まず動画を開いてください"},
        "dialog.concluido_titulo": {"es": "Marcar como concluido", "en": "Mark as done", "fr": "Marquer comme terminé", "pt": "Marcar como concluído", "it": "Segna come completato", "ja": "完了としてマーク"},
        "dialog.concluido_nada": {"es": "{nome} aún no tiene nada guardado.", "en": "{nome} has nothing saved yet.", "fr": "{nome} n'a encore rien d'enregistré.", "pt": "{nome} ainda não tem nada guardado.", "it": "{nome} non ha ancora nulla di salvato.", "ja": "{nome} にはまだ保存されたものがありません。"},
        "stat.concluido": {"es": "{nome} — marcado como concluido", "en": "{nome} — marked as done", "fr": "{nome} — marqué comme terminé", "pt": "{nome} — marcado como concluído", "it": "{nome} — segnato come completato", "ja": "{nome} — 完了としてマーク"},
        "stat.nao_concluido": {"es": "{nome} — ya no está marcado como concluido", "en": "{nome} — no longer marked as done", "fr": "{nome} — n'est plus marqué comme terminé", "pt": "{nome} — já não está marcado como concluído", "it": "{nome} — non è più segnato come completato", "ja": "{nome} — 完了マークを解除"},
        "dialog.relatorio_titulo": {"es": "Informe del entrenador — {nome}", "en": "Coach Report — {nome}", "fr": "Rapport de l'entraîneur — {nome}", "pt": "Relatório do Treinador — {nome}", "it": "Rapporto dell'allenatore — {nome}", "ja": "コーチレポート — {nome}"},
        "dialog.export_nao_concluidos": {"es": "{n} combate(s) aún no están marcados como concluidos.\n\n¿Exportar de todos modos?", "en": "{n} bout(s) are not yet marked as done.\n\nExport anyway?", "fr": "{n} combat(s) ne sont pas encore marqués comme terminés.\n\nExporter quand même ?", "pt": "{n} combate(s) ainda não estão marcados como concluídos.\n\nExportar mesmo assim?", "it": "{n} incontro/i non sono ancora segnati come completati.\n\nEsportare comunque?", "ja": "{n} 試合がまだ完了としてマークされていません。\n\nそれでもエクスポートしますか？"},
        "stat.conjunto_exportado": {"es": "Conjunto exportado: {n} sesiones, {m} anotaciones", "en": "Dataset exported: {n} sessions, {m} annotations", "fr": "Jeu de données exporté : {n} sessions, {m} annotations", "pt": "Conjunto exportado: {n} sessões, {m} anotações", "it": "Dataset esportato: {n} sessioni, {m} annotazioni", "ja": "データセットを書き出し：{n} セッション、{m} 件の記録"},
        "dialog.exportar_combate": {"es": "Exportar combate", "en": "Export bout", "fr": "Exporter le combat", "pt": "Exportar combate", "it": "Esporta incontro", "ja": "試合を書き出す"},
        "dialog.exportado_titulo": {"es": "Exportado", "en": "Exported", "fr": "Exporté", "pt": "Exportado", "it": "Esportato", "ja": "書き出し完了"},
        "dialog.exportado_msg": {"es": "{nome}\n\n{n} acciones.\n\nEste archivo se vuelve a cargar con «Cargar datos…» para seguir editando.", "en": "{nome}\n\n{n} actions.\n\nThis file can be loaded again with “Load data…” to keep editing.", "fr": "{nome}\n\n{n} actions.\n\nCe fichier se recharge avec « Charger des données… » pour continuer l'édition.", "pt": "{nome}\n\n{n} ações.\n\nEste ficheiro volta a carregar-se com «Carregar dados…» para continuar a editar.", "it": "{nome}\n\n{n} azioni.\n\nQuesto file si ricarica con «Carica dati…» per continuare a modificare.", "ja": "{nome}\n\n{n} 件のアクション。\n\n「データを読み込む…」で再度読み込んで編集を続けられます。"},
        "stat.exportado": {"es": "Exportado: {nome} ({n} acciones)", "en": "Exported: {nome} ({n} actions)", "fr": "Exporté : {nome} ({n} actions)", "pt": "Exportado: {nome} ({n} ações)", "it": "Esportato: {nome} ({n} azioni)", "ja": "書き出し：{nome}（{n} 件）"},
        "stat.carregado": {"es": "Cargado {nome}: {n} acciones sobre {video}", "en": "Loaded {nome}: {n} actions on {video}", "fr": "Chargé {nome} : {n} actions sur {video}", "pt": "Carregado {nome}: {n} ações sobre {video}", "it": "Caricato {nome}: {n} azioni su {video}", "ja": "{nome} を読み込み：{video} の {n} 件"},
        "stat.sem_paradas_analisadas": {"es": "Este vídeo no tiene paradas analizadas", "en": "This video has no analysed stops", "fr": "Cette vidéo n'a pas d'arrêts analysés", "pt": "Este vídeo não tem paradas analisadas", "it": "Questo video non ha interruzioni analizzate", "ja": "この動画には分析済みの中断がありません"},
        "stat.sem_mais_frente": {"es": "No hay más anotaciones por delante", "en": "No more annotations ahead", "fr": "Plus d'annotations en avant", "pt": "Não há mais anotações à frente", "it": "Nessun'altra annotazione in avanti", "ja": "この先に記録はありません"},
        "stat.sem_mais_atras": {"es": "No hay más anotaciones por detrás", "en": "No more annotations behind", "fr": "Plus d'annotations en arrière", "pt": "Não há mais anotações atrás", "it": "Nessun'altra annotazione indietro", "ja": "この前に記録はありません"},
        "dialog.apagar_feche": {"es": "Cierre el combate antes de borrar sus anotaciones.", "en": "Close the bout before deleting its annotations.", "fr": "Fermez le combat avant d'effacer ses annotations.", "pt": "Feche o combate antes de apagar as suas anotações.", "it": "Chiudi l'incontro prima di cancellare le sue annotazioni.", "ja": "記録を削除する前に試合を閉じてください。"},
        "dialog.apagar_nada": {"es": "{nome} no tiene anotaciones guardadas.", "en": "{nome} has no saved annotations.", "fr": "{nome} n'a aucune annotation enregistrée.", "pt": "{nome} não tem anotações guardadas.", "it": "{nome} non ha annotazioni salvate.", "ja": "{nome} には保存された記録がありません。"},
        "dialog.apagar_pregunta_video": {"es": "¿Borrar las {n} anotaciones de {nome}?", "en": "Delete the {n} annotations of {nome}?", "fr": "Effacer les {n} annotations de {nome} ?", "pt": "Apagar as {n} anotações de {nome}?", "it": "Cancellare le {n} annotazioni di {nome}?", "ja": "{nome} の {n} 件の記録を削除しますか？"},
        "stat.apagadas_video": {"es": "{nome} — {n} anotaciones borradas", "en": "{nome} — {n} annotations deleted", "fr": "{nome} — {n} annotations effacées", "pt": "{nome} — {n} anotações apagadas", "it": "{nome} — {n} annotazioni cancellate", "ja": "{nome} — {n} 件の記録を削除"},
        "stat.passada_iniciada": {"es": "Pasada {n} de {total} — iniciada. Anotando…", "en": "Pass {n} of {total} — started. Annotating…", "fr": "Passe {n} sur {total} — commencée. Annotation…", "pt": "Passada {n} de {total} — iniciada. Anotando…", "it": "Passata {n} di {total} — iniziata. Annotazione…", "ja": "パス {n}/{total} — 開始。記録中…"},
        "stat.autosave_falhou": {"es": "AVISO: el guardado automático FALLÓ — compruebe espacio y permisos (ver el log)", "en": "WARNING: autosave FAILED — check disk space and permissions (see the log)", "fr": "AVERTISSEMENT : la sauvegarde automatique a ÉCHOUÉ — vérifiez l'espace et les permissions (voir le journal)", "pt": "AVISO: o salvamento automático FALHOU — verifique espaço e permissões (ver o log)", "it": "AVVISO: il salvataggio automatico è FALLITO — controlla spazio e permessi (vedi il log)", "ja": "警告：自動保存に失敗 — 空き容量と権限を確認してください（ログを参照）"},
        "stat.passada_ativa": {"es": "Pasada activa: {label}", "en": "Active pass: {label}", "fr": "Passe active : {label}", "pt": "Passada ativa: {label}", "it": "Passata attiva: {label}", "ja": "有効なパス：{label}"},
        "stat.passada_desconhecida": {"es": "desconocida", "en": "unknown", "fr": "inconnue", "pt": "desconhecida", "it": "sconosciuta", "ja": "不明"},
        "round.titulo": {"es": "✦  Nueva pasada", "en": "✦  New pass", "fr": "✦  Nouvelle passe", "pt": "✦  Nova passada", "it": "✦  Nuova passata", "ja": "✦  新しいパス"},
        "round.cabecalho": {"es": "Nueva pasada", "en": "New pass", "fr": "Nouvelle passe", "pt": "Nova passada", "it": "Nuova passata", "ja": "新しいパス"},
        "round.existem": {"es": "Ya existen {n} pasada(s). La nueva será la n.º {m}.", "en": "There are already {n} pass(es). The new one will be no. {m}.", "fr": "Il existe déjà {n} passe(s). La nouvelle sera la n° {m}.", "pt": "Já existem {n} passada(s). A nova será a n.º {m}.", "it": "Esistono già {n} passate. La nuova sarà la n. {m}.", "ja": "すでに {n} 件のパスがあります。新しいパスは第 {m} パスです。"},
        "round.preview": {"es": "📝  Se creará:  Pasada {n}", "en": "📝  Will create:  Pass {n}", "fr": "📝  Sera créée :  Passe {n}", "pt": "📝  Vai criar-se:  Passagem {n}", "it": "📝  Si creerà:  Passata {n}", "ja": "📝  作成：パス {n}"},
        "round.criar": {"es": "Crear pasada", "en": "Create pass", "fr": "Créer la passe", "pt": "Criar passagem", "it": "Crea passata", "ja": "パスを作成"},
        "round.label": {"es": "Pasada {n}", "en": "Pass {n}", "fr": "Passe {n}", "pt": "Passagem {n}", "it": "Passata {n}", "ja": "パス {n}"},
        "stat.nova_passada": {"es": "Nueva pasada creada: {label}", "en": "New pass created: {label}", "fr": "Nouvelle passe créée : {label}", "pt": "Nova passada criada: {label}", "it": "Nuova passata creata: {label}", "ja": "新しいパスを作成：{label}"},
        "tm.macro_fase": {"es": "Fase {fase}", "en": "Phase {fase}", "fr": "Phase {fase}", "pt": "Fase {fase}", "it": "Fase {fase}", "ja": "フェーズ {fase}"},
        "undo.apagar_todas": {"es": "Borrar todas las anotaciones", "en": "Delete all annotations", "fr": "Effacer toutes les annotations", "pt": "Apagar todas as anotações", "it": "Cancella tutte le annotazioni", "ja": "すべての記録を削除"},
        "video.nao_abre": {"es": "No se pudo abrir el vídeo:\n{path}\n\nCompruebe que el archivo está descargado por completo (en Google Drive: «Disponible sin conexión») y, si persiste, cópielo a una carpeta local sin acentos ni símbolos.", "en": "Could not open the video:\n{path}\n\nCheck that the file is fully downloaded (in Google Drive: “Available offline”) and, if it persists, copy it to a local folder without accents or symbols.", "fr": "Impossible d'ouvrir la vidéo :\n{path}\n\nVérifiez que le fichier est entièrement téléchargé (dans Google Drive : « Disponible hors connexion ») et, si cela persiste, copiez-le dans un dossier local sans accents ni symboles.", "pt": "Não foi possível abrir o vídeo:\n{path}\n\nVerifique que o ficheiro está descarregado por completo (no Google Drive: «Disponível offline») e, se persistir, copie-o para uma pasta local sem acentos nem símbolos.", "it": "Impossibile aprire il video:\n{path}\n\nVerifica che il file sia scaricato per intero (in Google Drive: «Disponibile offline») e, se persiste, copialo in una cartella locale senza accenti né simboli.", "ja": "動画を開けませんでした：\n{path}\n\nファイルが完全にダウンロードされているか確認し（Google Drive では「オフラインで使用可能」）、それでも開けない場合はアクセント記号や記号のないローカルフォルダにコピーしてください。"},
        "video.sem_frames": {"es": "El vídeo abre pero no se puede leer ningún fotograma:\n{path}\n\nLector: {leitor}, {n} fotogramas anunciados. Compruebe que el archivo está descargado por completo.", "en": "The video opens but no frame can be read:\n{path}\n\nReader: {leitor}, {n} frames announced. Check that the file is fully downloaded.", "fr": "La vidéo s'ouvre mais aucune image ne peut être lue :\n{path}\n\nLecteur : {leitor}, {n} images annoncées. Vérifiez que le fichier est entièrement téléchargé.", "pt": "O vídeo abre mas não se consegue ler nenhum fotograma:\n{path}\n\nLeitor: {leitor}, {n} fotogramas anunciados. Verifique que o ficheiro está descarregado por completo.", "it": "Il video si apre ma non si legge nessun fotogramma:\n{path}\n\nLettore: {leitor}, {n} fotogrammi annunciati. Verifica che il file sia scaricato per intero.", "ja": "動画は開けますがフレームを読み取れません：\n{path}\n\nリーダー：{leitor}、{n} フレームと報告。ファイルが完全にダウンロードされているか確認してください。"},
        "stat.tecnica_pendente": {"es": "Técnica: {tecnica} [{atleta}] — pulse [O] para confirmar", "en": "Technique: {tecnica} [{atleta}] — press [O] to confirm", "fr": "Technique : {tecnica} [{atleta}] — appuyez sur [O] pour confirmer", "pt": "Técnica: {tecnica} [{atleta}] — press [O] to confirm", "it": "Tecnica: {tecnica} [{atleta}] — premi [O] per confermare", "ja": "技：{tecnica} [{atleta}] — [O] で確定"},
        "stat.fim_sem_tecnica": {"es": "FIN en el frame {frame} — ninguna técnica pendiente", "en": "END at frame {frame} — no pending technique", "fr": "FIN à l'image {frame} — aucune technique en attente", "pt": "FIM no frame {frame} — nenhuma técnica pendente", "it": "FINE al frame {frame} — nessuna tecnica in sospeso", "ja": "フレーム {frame} で終了 — 保留中の技なし"},
        "log.cat.attack": {"es": "ATAQUE", "en": "ATTACK", "fr": "ATTAQUE", "pt": "ATAQUE", "it": "ATTACCO", "ja": "攻撃"},
        "log.cat.defense": {"es": "DEFENSA", "en": "DEFENCE", "fr": "DÉFENSE", "pt": "DEFESA", "it": "DIFESA", "ja": "防御"},
        "log.cat.tactics": {"es": "TÁCTICA", "en": "TACTICS", "fr": "TACTIQUE", "pt": "TÁCTICA", "it": "TATTICA", "ja": "戦術"},
        "log.cat.referee_stop": {"es": "ÁRBITRO", "en": "REFEREE", "fr": "ARBITRE", "pt": "ÁRBITRO", "it": "ARBITRO", "ja": "主審"},
        "log.cat.penalty": {"es": "PENALIZACIÓN", "en": "PENALTY", "fr": "PÉNALITÉ", "pt": "PENALIZAÇÃO", "it": "PENALITÀ", "ja": "罰則"},
        "log.cat.phase": {"es": "FASE", "en": "PHASE", "fr": "PHASE", "pt": "FASE", "it": "FASE", "ja": "フェーズ"},
        "log.ir_acao": {"es": "Ir a esta acción", "en": "Go to this action", "fr": "Aller à cette action", "pt": "Ir para esta ação", "it": "Vai a questa azione", "ja": "このアクションへ移動"},
        "log.editar": {"es": "Editar…", "en": "Edit…", "fr": "Modifier…", "pt": "Editar…", "it": "Modifica…", "ja": "編集…"},
        "log.excluir": {"es": "Eliminar", "en": "Delete", "fr": "Supprimer", "pt": "Excluir", "it": "Elimina", "ja": "削除"},
        "log.tabela": {"es": "Ver tabla completa…", "en": "View full table…", "fr": "Voir le tableau complet…", "pt": "Ver tabela completa…", "it": "Vedi tabella completa…", "ja": "完全な表を表示…"},
        "hub.carregar_dados": {"es": "Cargar datos…", "en": "Load data…", "fr": "Charger des données…", "pt": "Carregar dados…", "it": "Carica dati…", "ja": "データを読み込む…"},
        "video.tecla_k": {"es": "[K] o [espacio]", "en": "[K] or [space]", "fr": "[K] ou [espace]", "pt": "[K] ou [espaço]", "it": "[K] o [spazio]", "ja": "[K] または [スペース]"},
        "paradas.n_referee": {"es": "decisión del árbitro", "en": "referee decision", "fr": "décision de l'arbitre", "pt": "decisão do árbitro", "it": "decisione dell'arbitro", "ja": "主審の判定"},
        "paradas.n_vr": {"es": "revisión de vídeo", "en": "video review", "fr": "révision vidéo", "pt": "revisão de vídeo", "it": "revisione video", "ja": "ビデオ判定"},
        "paradas.n_injury": {"es": "lesión", "en": "injury", "fr": "blessure", "pt": "lesão", "it": "infortunio", "ja": "負傷"},
        "paradas.marcada": {"es": "Parada marcada como {nome} ({n} {filas}){clonada}", "en": "Stop marked as {nome} ({n} {filas}){clonada}", "fr": "Arrêt marqué comme {nome} ({n} {filas}){clonada}", "pt": "Parada marcada como {nome} ({n} {filas}){clonada}", "it": "Interruzione segnata come {nome} ({n} {filas}){clonada}", "ja": "中断を{nome}として記録（{n} {filas}）{clonada}"},
        "paradas.fila": {"es": "fila", "en": "row", "fr": "ligne", "pt": "fila", "it": "riga", "ja": "行"},
        "paradas.filas": {"es": "filas", "en": "rows", "fr": "lignes", "pt": "filas", "it": "righe", "ja": "行"},
        "paradas.clonada": {"es": " — fila de {atleta} creada con los frames de {socio}", "en": " — {atleta} row created with the frames of {socio}", "fr": " — ligne de {atleta} créée avec les images de {socio}", "pt": " — fila de {atleta} criada com os frames de {socio}", "it": " — riga di {atleta} creata con i frame di {socio}", "ja": " — {socio} のフレームで {atleta} の行を作成"},
        "dialog.sem_acoes_titulo": {"es": "Sin acciones", "en": "No actions", "fr": "Aucune action", "pt": "Sem ações", "it": "Nessuna azione", "ja": "アクションなし"},
        "dialog.sem_acoes": {"es": "{nome} no tiene ninguna acción.", "en": "{nome} has no actions.", "fr": "{nome} ne contient aucune action.", "pt": "{nome} não tem nenhuma ação.", "it": "{nome} non ha nessuna azione.", "ja": "{nome} にはアクションがありません。"},
        "dialog.onde_video_titulo": {"es": "¿Dónde está el vídeo?", "en": "Where is the video?", "fr": "Où est la vidéo ?", "pt": "Onde está o vídeo?", "it": "Dov'è il video?", "ja": "動画はどこですか？"},
        "dialog.onde_video": {"es": "El archivo dice que es de «{nome}», pero no aparece junto a él.\n\nElíjalo a mano.", "en": "The file says it belongs to “{nome}”, but it is not next to it.\n\nChoose it by hand.", "fr": "Le fichier dit qu'il appartient à « {nome} », mais il n'est pas à côté.\n\nChoisissez-le à la main.", "pt": "O ficheiro diz que é de «{nome}», mas não aparece ao lado dele.\n\nEscolha-o à mão.", "it": "Il file dice che è di «{nome}», ma non appare accanto a esso.\n\nScegli il video a mano.", "ja": "ファイルは「{nome}」のものと記していますが、隣にありません。\n\n手動で選んでください。"},
        "dialog.um_video": {"es": "un vídeo", "en": "a video", "fr": "une vidéo", "pt": "um vídeo", "it": "un video", "ja": "動画"},
        "dialog.video_do_combate": {"es": "Vídeo del combate", "en": "Bout video", "fr": "Vidéo du combat", "pt": "Vídeo do combate", "it": "Video dell'incontro", "ja": "試合の動画"},
        "dialog.filtro_video": {"es": "Vídeo (*.mp4 *.mov *.avi *.mkv)", "en": "Video (*.mp4 *.mov *.avi *.mkv)", "fr": "Vidéo (*.mp4 *.mov *.avi *.mkv)", "pt": "Vídeo (*.mp4 *.mov *.avi *.mkv)", "it": "Video (*.mp4 *.mov *.avi *.mkv)", "ja": "動画 (*.mp4 *.mov *.avi *.mkv)"},
        "dialog.nao_abre_titulo": {"es": "No se pudo abrir el vídeo", "en": "Could not open the video", "fr": "Impossible d'ouvrir la vidéo", "pt": "Não foi possível abrir o vídeo", "it": "Impossibile aprire il video", "ja": "動画を開けませんでした"},
        "dialog.descalificado_titulo": {"es": "Atleta ya descalificado", "en": "Athlete already disqualified", "fr": "Athlète déjà disqualifié", "pt": "Atleta já desclassificado", "it": "Atleta già squalificato", "ja": "すでに失格の選手"},
        "dialog.descalificado": {"es": "{atleta} ya acumula {ultimo}, que termina el combate.\n\nEsta sería una falta posterior, así que puede haber un error en las anteriores.\n\n¿Anotarla igualmente?", "en": "{atleta} already has {ultimo}, which ends the bout.\n\nThis would be a later foul, so there may be an error in the earlier ones.\n\nRecord it anyway?", "fr": "{atleta} a déjà {ultimo}, qui termine le combat.\n\nCe serait une faute postérieure, il peut donc y avoir une erreur dans les précédentes.\n\nL'enregistrer quand même ?", "pt": "{atleta} já acumula {ultimo}, que termina o combate.\n\nEsta seria uma falta posterior, por isso pode haver um erro nas anteriores.\n\nAnotá-la mesmo assim?", "it": "{atleta} ha già {ultimo}, che termina l'incontro.\n\nQuesto sarebbe un fallo successivo, quindi può esserci un errore nei precedenti.\n\nAnnotarlo comunque?", "ja": "{atleta} はすでに {ultimo} に達しており、試合は終了です。\n\nこれは後の反則になるため、前の反則に誤りがあるかもしれません。\n\nそれでも記録しますか？"},

        # ── El tiempo-movimiento (solo donde el deporte lo hace) ──────
        "tm.titulo": {"es": "TIEMPO-MOVIMIENTO", "en": "TIME-MOTION", "fr": "TEMPS-MOUVEMENT", "pt": "TEMPO-MOVIMENTO", "it": "TEMPO-MOVIMENTO", "ja": "タイムモーション"},
        "tm.asalto": {"es": "Asalto {n} de {total}", "en": "Round {n} of {total}", "fr": "Round {n} sur {total}", "pt": "Assalto {n} de {total}", "it": "Round {n} di {total}", "ja": "ラウンド {n}/{total}"},
        "tm.que_fighting": {"es": "empieza un intercambio", "en": "an exchange starts", "fr": "un échange commence", "pt": "começa um intercâmbio", "it": "inizia uno scambio", "ja": "攻防が始まる"},
        "tm.que_non_fighting": {"es": "sin intercambio", "en": "no exchange", "fr": "sans échange", "pt": "sem intercâmbio", "it": "senza scambio", "ja": "攻防なし"},
        "tm.que_stoppage": {"es": "el árbitro paró", "en": "the referee stopped", "fr": "l'arbitre a arrêté", "pt": "o árbitro parou", "it": "l'arbitro ha fermato", "ja": "主審が止めた"},
        # El cuarto estado es del karate y es nuestro (decisión 0008): un
        # tramo en el que el vídeo no permite decidir no es ninguno de los tres.
        "tm.que_unobservable": {"es": "el vídeo no permite decidir en qué estado está el combate", "en": "the video does not allow deciding which state the bout is in", "fr": "la vidéo ne permet pas de décider dans quel état est le combat", "pt": "o vídeo não permite decidir em que estado está o combate", "it": "il video non permette di decidere in quale stato è il combattimento", "ja": "映像では試合の状態を判断できない"},
        "tm.pie": {"es": "Cada tecla es una fila del registro, abajo.  ·  {retirar} retira la última.", "en": "Every key is a row in the log below.  ·  {retirar} removes the last one.", "fr": "Chaque touche est une ligne du registre, en dessous.  ·  {retirar} retire la dernière.", "pt": "Cada tecla é uma linha do registo, abaixo.  ·  {retirar} retira a última.", "it": "Ogni tasto è una riga del registro, sotto.  ·  {retirar} toglie l'ultima.", "ja": "各キーは下の記録の1行になります。 · {retirar} で最後を取り消す。"},
        "tm.pie_atletas": {"es": "Una pasada por competidor: [A] y [B] cambian de atleta.", "en": "One pass per competitor: [A] and [B] switch athlete.", "fr": "Une passe par compétiteur : [A] et [B] changent d'athlète.", "pt": "Uma passagem por competidor: [A] e [B] mudam de atleta.", "it": "Una passata per competitore: [A] e [B] cambiano atleta.", "ja": "競技者ごとに1パス：[A] と [B] で選手を切り替え。"},
        "tm.agora": {"es": "Ahora {atleta} · {teclas}", "en": "Now {atleta} · {teclas}", "fr": "Maintenant {atleta} · {teclas}", "pt": "Agora {atleta} · {teclas}", "it": "Ora {atleta} · {teclas}", "ja": "次は {atleta} · {teclas}"},
        "tm.fases_antiguas": {"es": "Este combate tiene {n} fases marcadas sin atleta (de antes del 9-10, del combate entero): se conservan como «Bout (both)» en el registro y el informe. Elija el atleta y marque desde aquí.", "en": "This bout has {n} phases marked without an athlete (before 9 October, bout-level): they are kept as “Bout (both)” in the log and the report. Choose the athlete and mark from here.", "fr": "Ce combat a {n} phases marquées sans athlète (avant le 9/10, du combat entier) : elles sont conservées comme « Bout (both) » dans le registre et le rapport. Choisissez l'athlète et marquez à partir d'ici.", "pt": "Este combate tem {n} fases marcadas sem atleta (de antes de 9-10, do combate inteiro): conservam-se como «Bout (both)» no registo e no relatório. Escolha o atleta e marque a partir daqui.", "it": "Questo incontro ha {n} fasi segnate senza atleta (prima del 9-10, dell'intero incontro): si conservano come «Bout (both)» nel registro e nel rapporto. Scegli l'atleta e segna da qui.", "ja": "この試合には選手なしで記録されたフェーズが {n} 件あります（10月9日以前、試合全体）。記録と報告書に「Bout (both)」として残ります。選手を選んでここから記録してください。"},
        "tm.asalto_corto": {"es": "Asalto {n}", "en": "Round {n}", "fr": "Round {n}", "pt": "Assalto {n}", "it": "Round {n}", "ja": "R{n}"},
        "tm.asalto_tecla_f": {"es": "[F] inicio", "en": "[F] start", "fr": "[F] début", "pt": "[F] início", "it": "[F] inizio", "ja": "[F] 開始"},
        "tm.guia_abrir": {"es": "Asalto {n} de {total}: vaya a donde empieza y pulse [F].", "en": "Round {n} of {total}: go to where it starts and press [F].", "fr": "Round {n} sur {total} : allez à son début et appuyez sur [F].", "pt": "Assalto {n} de {total}: vá até onde começa e pressione [F].", "it": "Round {n} di {total}: vai al suo inizio e premi [F].", "ja": "ラウンド {n}/{total}：開始位置へ進んで [F]。"},
        "tm.guia_cerrar": {"es": "Asalto {n} abierto desde {desde}: marque las fases y pulse [G] en su final.", "en": "Round {n} open since {desde}: mark the phases and press [G] at its end.", "fr": "Round {n} ouvert depuis {desde} : marquez les phases et appuyez sur [G] à sa fin.", "pt": "Assalto {n} aberto desde {desde}: marque as fases e pressione [G] no seu fim.", "it": "Round {n} aperto da {desde}: segna le fasi e premi [G] alla sua fine.", "ja": "ラウンド {n} は {desde} から開いています：フェーズを記録し、終了位置で [G]。"},
        "tm.guia_hechos": {"es": 'Los {total} asaltos están marcados: son del combate y valen para los dos atletas. Marque las fases; para corregir un asalto, pulse su pastilla.', "en": "All {total} rounds are marked: they are the bout's and hold for both athletes. Mark the phases; to correct a round, click its chip.", "fr": 'Les {total} rounds sont marqués : ils sont du combat et valent pour les deux athlètes. Marquez les phases ; pour corriger un round, cliquez sa pastille.', "pt": 'Os {total} assaltos estão marcados: são do combate e valem para os dois atletas. Marque as fases; para corrigir um assalto, clique na sua pastilha.', "it": "I {total} round sono segnati: sono dell'incontro e valgono per i due atleti. Segna le fasi; per correggere un round, clicca la sua pastiglia.", "ja": '{total} ラウンドすべて記録済み：試合のもので両選手に共通です。フェーズを記録してください。修正するにはその枠をクリック。'},
        "tm.guia_hechos_atleta": {"es": 'Los {total} asaltos de {atleta} están marcados. Al cerrar el último se ofrece el otro atleta, que marca los suyos. Para corregir un asalto, pulse su pastilla.', "en": "{atleta}'s {total} rounds are marked. Closing the last one offers the other athlete, who marks their own. To correct a round, click its chip.", "fr": "Les {total} rounds de {atleta} sont marqués. À la fermeture du dernier, l'autre athlète est proposé et marque les siens. Pour corriger un round, cliquez sa pastille.", "pt": 'Os {total} assaltos de {atleta} estão marcados. Ao fechar o último oferece-se o outro atleta, que marca os seus. Para corrigir um assalto, clique na sua pastilha.', "it": "I {total} round di {atleta} sono segnati. Chiudendo l'ultimo si propone l'altro atleta, che segna i suoi. Per correggere un round, clicca la sua pastiglia.", "ja": '{atleta} の {total} ラウンドは記録済み。最後を閉じると相手選手に進み、相手は自分のラウンドを記録します。修正するにはその枠をクリック。'},
        "tm.fuera_de_asalto": {"es": "Fuera de los asaltos de {atleta}: pulse [F] donde empieza el asalto {n} y marque después las fases.", "en": "Outside {atleta}'s rounds: press [F] where round {n} starts, then mark the phases.", "fr": "Hors des rounds de {atleta} : appuyez sur [F] au début du round {n}, puis marquez les phases.", "pt": "Fora dos assaltos de {atleta}: pressione [F] onde começa o assalto {n} e marque depois as fases.", "it": "Fuori dai round di {atleta}: premi [F] dove inizia il round {n}, poi segna le fasi.", "ja": "{atleta} のラウンド外です：ラウンド {n} の開始位置で [F] を押してからフェーズを記録。"},
        "tm.fuera_de_los_asaltos": {"es": "Fuera de los asaltos de {atleta}: aquí no hay fase que marcar.", "en": "Outside {atleta}'s rounds: there is no phase to mark here.", "fr": "Hors des rounds de {atleta} : pas de phase à marquer ici.", "pt": "Fora dos assaltos de {atleta}: aqui não há fase a marcar.", "it": "Fuori dai round di {atleta}: qui non c'è fase da segnare.", "ja": "{atleta} のラウンド外：ここで記録するフェーズはありません。"},
        "tm.asaltos_completos": {"es": 'Los {total} asaltos de {atleta} ya están marcados. {pista}', "en": "{atleta}'s {total} rounds are already marked. {pista}", "fr": 'Les {total} rounds de {atleta} sont déjà marqués. {pista}', "pt": 'Os {total} assaltos de {atleta} já estão marcados. {pista}', "it": 'I {total} round di {atleta} sono già segnati. {pista}', "ja": '{atleta} の {total} ラウンドは記録済みです。{pista}'},
        "tm.otro_atleta_asaltos_hechos": {"es": "Ahora {target}: los {total} asaltos ya están marcados. [I] o un número para la primera acción.", "en": "Now {target}: the {total} rounds are already marked. [I] or a number for the first action.", "fr": "Maintenant {target} : les {total} rounds sont déjà marqués. [I] ou un chiffre pour la première action.", "pt": "Agora {target}: os {total} assaltos já estão marcados. [I] ou um número para a primeira ação.", "it": "Ora {target}: i {total} round sono già segnati. [I] o un numero per la prima azione.", "ja": "次は {target}：{total} ラウンドは記録済み。最初のアクションは [I] か数字。"},
        "tm.asaltos_del_combate": {"es": 'Asaltos del combate:', "en": 'Rounds in this bout:', "fr": 'Rounds du combat :', "pt": 'Assaltos do combate:', "it": "Round dell'incontro:", "ja": 'この試合のラウンド数：'},
        "tm.asalto_cerrado_elegir": {"es": 'El asalto {n} ya está cerrado. Para corregirlo, pulse antes su pastilla.', "en": 'Round {n} is already closed. To correct it, click its chip first.', "fr": "Le round {n} est déjà fermé. Pour le corriger, cliquez d'abord sur sa pastille.", "pt": 'O assalto {n} já está fechado. Para o corrigir, clique primeiro na sua pastilha.', "it": 'Il round {n} è già chiuso. Per correggerlo, clicca prima sulla sua pastiglia.', "ja": 'ラウンド {n} は終了済みです。修正するには先にその枠をクリックしてください。'},
        "tm.asalto_abierto_cerrar": {"es": 'El asalto {n} está abierto: pulse [G] en su final antes de empezar otro.', "en": 'Round {n} is open: press [G] at its end before starting another.', "fr": "Le round {n} est ouvert : appuyez sur [G] à sa fin avant d'en commencer un autre.", "pt": 'O assalto {n} está aberto: pressione [G] no seu fim antes de começar outro.', "it": 'Il round {n} è aperto: premi [G] alla sua fine prima di iniziarne un altro.', "ja": 'ラウンド {n} が開いています：次を始める前に終了位置で [G]。'},
        "tm.asalto_despues_de": {"es": 'El asalto {n} tiene que empezar después de que acabe el {previo} ({reloj}).', "en": 'Round {n} must start after round {previo} ends ({reloj}).', "fr": 'Le round {n} doit commencer après la fin du round {previo} ({reloj}).', "pt": 'O assalto {n} tem de começar depois de acabar o {previo} ({reloj}).', "it": 'Il round {n} deve iniziare dopo la fine del round {previo} ({reloj}).', "ja": 'ラウンド {n} はラウンド {previo} の終了（{reloj}）より後に始めてください。'},
        "tm.asalto_inicio_antes_fin": {"es": 'El inicio del asalto {n} tiene que ser antes de su final ({reloj}).', "en": 'The start of round {n} must be before its end ({reloj}).', "fr": 'Le début du round {n} doit précéder sa fin ({reloj}).', "pt": 'O início do assalto {n} tem de ser antes do seu fim ({reloj}).', "it": "L'inizio del round {n} deve precedere la sua fine ({reloj}).", "ja": 'ラウンド {n} の開始は終了（{reloj}）より前にしてください。'},
        "tm.asalto_fin_despues_inicio": {"es": 'El final del asalto {n} tiene que ser después de su inicio ({reloj}).', "en": 'The end of round {n} must be after its start ({reloj}).', "fr": 'La fin du round {n} doit suivre son début ({reloj}).', "pt": 'O fim do assalto {n} tem de ser depois do seu início ({reloj}).', "it": 'La fine del round {n} deve seguire il suo inizio ({reloj}).', "ja": 'ラウンド {n} の終了は開始（{reloj}）より後にしてください。'},
        "tm.asalto_antes_del_siguiente": {"es": 'El asalto {n} tiene que acabar antes de que empiece el {siguiente} ({reloj}).', "en": 'Round {n} must end before round {siguiente} starts ({reloj}).', "fr": 'Le round {n} doit finir avant le début du round {siguiente} ({reloj}).', "pt": 'O assalto {n} tem de acabar antes de começar o {siguiente} ({reloj}).', "it": 'Il round {n} deve finire prima che inizi il round {siguiente} ({reloj}).', "ja": 'ラウンド {n} はラウンド {siguiente} の開始（{reloj}）より前に終えてください。'},
        "tm.asalto_fases_antes": {"es": '{cuantas} fase(s) del asalto {n} empiezan antes de este punto (la primera en {reloj}): quedarían fuera. Elija un punto anterior o retírelas antes ({retirar}).', "en": '{cuantas} phase(s) of round {n} start before this point (the first at {reloj}): they would be left outside. Choose an earlier point or remove them first ({retirar}).', "fr": "{cuantas} phase(s) du round {n} commencent avant ce point (la première à {reloj}) : elles resteraient dehors. Choisissez un point antérieur ou retirez-les d'abord ({retirar}).", "pt": '{cuantas} fase(s) do assalto {n} começam antes deste ponto (a primeira em {reloj}): ficariam de fora. Escolha um ponto anterior ou retire-as antes ({retirar}).', "it": '{cuantas} fase/i del round {n} iniziano prima di questo punto (la prima a {reloj}): resterebbero fuori. Scegli un punto precedente o toglile prima ({retirar}).', "ja": 'ラウンド {n} の {cuantas} 件のフェーズがこの位置より前に始まります（最初は {reloj}）：範囲外になります。前の位置を選ぶか、先に取り消してください（{retirar}）。'},
        "tm.asalto_fases_despues": {"es": '{cuantas} fase(s) del asalto {n} empiezan después de este punto (la última en {reloj}): quedarían fuera. Vaya al final del asalto o retírelas antes ({retirar}).', "en": '{cuantas} phase(s) of round {n} start after this point (the last at {reloj}): they would be left outside. Go to the end of the round or remove them first ({retirar}).', "fr": "{cuantas} phase(s) du round {n} commencent après ce point (la dernière à {reloj}) : elles resteraient dehors. Allez à la fin du round ou retirez-les d'abord ({retirar}).", "pt": '{cuantas} fase(s) do assalto {n} começam depois deste ponto (a última em {reloj}): ficariam de fora. Vá até ao fim do assalto ou retire-as antes ({retirar}).', "it": "{cuantas} fase/i del round {n} iniziano dopo questo punto (l'ultima a {reloj}): resterebbero fuori. Vai alla fine del round o toglile prima ({retirar}).", "ja": 'ラウンド {n} の {cuantas} 件のフェーズがこの位置より後に始まります（最後は {reloj}）：範囲外になります。ラウンドの終わりへ進むか、先に取り消してください（{retirar}）。'},
        "tm.no_reducir": {"es": 'El asalto {n} ya está marcado: bórrelo antes (pulse su pastilla y «Borrar») para tener menos asaltos.', "en": 'Round {n} is already marked: clear it first (click its chip, then Clear) to have fewer rounds.', "fr": "Le round {n} est déjà marqué : effacez-le d'abord (cliquez sa pastille, puis Effacer) pour avoir moins de rounds.", "pt": 'O assalto {n} já está marcado: apague-o antes (clique na sua pastilha e em «Apagar») para ter menos assaltos.', "it": 'Il round {n} è già segnato: cancellalo prima (clicca la sua pastiglia, poi Cancella) per avere meno round.', "ja": 'ラウンド {n} は記録済みです。ラウンドを減らすには、先に枠をクリックして「消去」してください。'},
        "tm.numero_elegido": {"es": 'Este combate tiene {n} asalto(s).', "en": 'This bout has {n} round(s).', "fr": 'Ce combat a {n} round(s).', "pt": 'Este combate tem {n} assalto(s).', "it": 'Questo incontro ha {n} round.', "ja": 'この試合は {n} ラウンドです。'},
        "tm.correccion_hecha": {"es": 'Asalto {n}: corrección terminada.', "en": 'Round {n}: correction finished.', "fr": 'Round {n} : correction terminée.', "pt": 'Assalto {n}: correção terminada.', "it": 'Round {n}: correzione terminata.', "ja": 'ラウンド {n}：修正を終了しました。'},
        "tm.guia_corrigiendo": {"es": 'Corrigiendo el asalto {n}: vaya a su inicio o a su final correctos y pulse [F] o [G]. Pulse otra vez su pastilla para terminar.', "en": 'Correcting round {n}: go to its correct start or end and press [F] or [G]. Click its chip again to finish.', "fr": 'Correction du round {n} : allez à son vrai début ou à sa vraie fin et appuyez sur [F] ou [G]. Cliquez à nouveau sa pastille pour terminer.', "pt": 'A corrigir o assalto {n}: vá ao início ou ao fim corretos e pressione [F] ou [G]. Clique de novo na pastilha para terminar.', "it": 'Correzione del round {n}: vai al suo inizio o alla sua fine corretti e premi [F] o [G]. Clicca di nuovo la pastiglia per finire.', "ja": 'ラウンド {n} を修正中：正しい開始または終了位置で [F] か [G]。終えるには枠をもう一度クリック。'},
        "tm.no_borrar_con_fases": {"es": 'El asalto {n} tiene {cuantas} anotación(es) dentro: retírelas antes de borrarlo.', "en": 'Round {n} has {cuantas} annotation(s) inside: remove them before clearing it.', "fr": "Le round {n} contient {cuantas} annotation(s) : retirez-les avant de l'effacer.", "pt": 'O assalto {n} tem {cuantas} anotação(ões) dentro: retire-as antes de o apagar.', "it": 'Il round {n} contiene {cuantas} annotazione/i: toglile prima di cancellarlo.', "ja": 'ラウンド {n} の中に {cuantas} 件の記録があります：消去する前に取り消してください。'},
        "tm.asalto_borrado": {"es": 'Asalto {n} borrado.', "en": 'Round {n} cleared.', "fr": 'Round {n} effacé.', "pt": 'Assalto {n} apagado.', "it": 'Round {n} cancellato.', "ja": 'ラウンド {n} を消去しました。'},
        "tm.boton_abrir": {"es": 'F   Iniciar asalto {n}', "en": 'F   Start round {n}', "fr": 'F   Début du round {n}', "pt": 'F   Iniciar assalto {n}', "it": 'F   Inizia round {n}', "ja": 'F   ラウンド {n} 開始'},
        "tm.boton_cerrar": {"es": 'G   Cerrar asalto {n}', "en": 'G   End round {n}', "fr": 'G   Fin du round {n}', "pt": 'G   Fechar assalto {n}', "it": 'G   Chiudi round {n}', "ja": 'G   ラウンド {n} 終了'},
        "tm.boton_mover_inicio": {"es": 'F   Mover inicio A{n}', "en": 'F   Move start R{n}', "fr": 'F   Déplacer début R{n}', "pt": 'F   Mover início A{n}', "it": 'F   Sposta inizio R{n}', "ja": 'F   R{n} 開始を移動'},
        "tm.boton_mover_fin": {"es": 'G   Mover final A{n}', "en": 'G   Move end R{n}', "fr": 'G   Déplacer fin R{n}', "pt": 'G   Mover fim A{n}', "it": 'G   Sposta fine R{n}', "ja": 'G   R{n} 終了を移動'},
        "tm.boton_borrar": {"es": 'Borrar A{n}', "en": 'Clear R{n}', "fr": 'Effacer R{n}', "pt": 'Apagar A{n}', "it": 'Cancella R{n}', "ja": 'R{n} 消去'},
        "tm.exportado_titulo": {"es": "Exportado", "en": "Exported", "fr": "Exporté", "pt": "Exportado", "it": "Esportato", "ja": "書き出し完了"},
        "tm.exportado_dos": {"es": "{n} filas.\n\n{csv}: los datos; se vuelven a cargar con «Importar».\n\n{xlsx}: el informe del análisis, con la hoja «Time-Motion matrix»: un luchador a la izquierda y el otro a la derecha, por asalto.", "en": "{n} rows.\n\n{csv}: the data; reload it with Import.\n\n{xlsx}: the analysis report, with the “Time-Motion matrix” sheet: one fighter on the left, the other on the right, round by round.", "fr": "{n} lignes.\n\n{csv} : les données ; à recharger avec Importer.\n\n{xlsx} : le rapport de l'analyse, avec la feuille « Time-Motion matrix » : un combattant à gauche, l'autre à droite, round par round.", "pt": "{n} linhas.\n\n{csv}: os dados; voltam a carregar-se com «Importar».\n\n{xlsx}: o relatório da análise, com a folha «Time-Motion matrix»: um lutador à esquerda e o outro à direita, por assalto.", "it": "{n} righe.\n\n{csv}: i dati; si ricaricano con Importa.\n\n{xlsx}: il rapporto dell'analisi, con il foglio «Time-Motion matrix»: un atleta a sinistra e l'altro a destra, round per round.", "ja": "{n} 行。\n\n{csv}：データ（「読み込み」で再読込）。\n\n{xlsx}：分析レポート。「Time-Motion matrix」シートでは左右に選手を分けてラウンドごとに表示。"},
        "tm.pista_corregir_pastilla": {"es": "Para corregir uno, pulse su pastilla.", "en": "To correct one, click its chip.", "fr": "Pour en corriger un, cliquez sa pastille.", "pt": "Para corrigir um, clique na sua pastilha.", "it": "Per correggerne uno, clicca la sua pastiglia.", "ja": "修正するにはその枠をクリック。"},
        "tm.pista_corregir_dentro": {"es": "[F] o [G] dentro de un asalto lo corrigen.", "en": "[F] or [G] inside a round correct it.", "fr": "[F] ou [G] dans un round le corrigent.", "pt": "[F] ou [G] dentro de um assalto corrigem-no.", "it": "[F] o [G] dentro un round lo correggono.", "ja": "ラウンド内の [F]／[G] で修正できます。"},
        "tm.sin_fase": {"es": "sin fase", "en": "no phase", "fr": "sans phase", "pt": "sem fase", "it": "senza fase", "ja": "フェーズなし"},
        "tm.aviso_tm": {"es": "Análisis: tiempo-movimiento, una pasada por competidor — {teclas}, donde empieza cada fase del atleta elegido. Cada tecla es una fila del registro. {retirar} retira la última.", "en": "Analysis: time-motion, one pass per competitor — {teclas}, where each phase of the chosen athlete starts. Every key is a row in the log. {retirar} removes the last one.", "fr": "Analyse : temps-mouvement, une passe par compétiteur — {teclas}, là où chaque phase de l'athlète choisi commence. Chaque touche est une ligne du registre. {retirar} retire la dernière.", "pt": "Análise: tempo-movimento, uma passagem por competidor — {teclas}, onde cada fase do atleta escolhido começa. Cada tecla é uma linha do registo. {retirar} retira a última.", "it": "Analisi: tempo-movimento, una passata per competitore — {teclas}, dove inizia ogni fase dell'atleta scelto. Ogni tasto è una riga del registro. {retirar} toglie l'ultima.", "ja": "分析：タイムモーション、競技者ごとに1パス — {teclas}、選択した選手の各フェーズの開始位置で。各キーは記録の1行。{retirar} で最後を取り消す。"},
        "tm.aviso_completa": {"es": "Análisis integrado — [I] inicio, las preguntas, [O] fin: acciones con duración; las fases salen de ellas. [F3] para marcarlas a mano y comparar.", "en": "Integrated analysis — [I] start, the questions, [O] end: actions with their duration; the phases come from them. [F3] to mark them by hand and compare.", "fr": "Analyse intégrée — [I] début, les questions, [O] fin : actions avec durée ; les phases en découlent. [F3] pour les marquer à la main et comparer.", "pt": "Análise integrada — [I] início, as perguntas, [O] fim: ações com duração; as fases saem delas. [F3] para as marcar à mão e comparar.", "it": "Analisi integrata — [I] inizio, le domande, [O] fine: azioni con durata; le fasi ne derivano. [F3] per segnarle a mano e confrontare.", "ja": "統合分析 — [I] 開始、質問、[O] 終了：持続時間つきのアクション。フェーズはそこから導かれる。[F3] で手動記録して比較。"},
        "tm.aviso_tt": {"es": "Análisis técnico-táctico — [I] o un número abre la acción y las preguntas la clasifican. No hay fin que marcar: se cuenta la acción, no su duración.", "en": "Technical-tactical analysis — [I] or a number opens the action and the questions classify it. No end to mark: the action is counted, not timed.", "fr": "Analyse technico-tactique — [I] ou un chiffre ouvre l'action et les questions la classent. Pas de fin à marquer : on compte l'action, pas sa durée.", "pt": "Análise técnico-tática — [I] ou um número abre a ação e as perguntas classificam-na. Não há fim a marcar: conta-se a ação, não a sua duração.", "it": "Analisi tecnico-tattica — [I] o un numero apre l'azione e le domande la classificano. Nessuna fine da segnare: si conta l'azione, non la sua durata.", "ja": "技術・戦術分析 — [I] か数字でアクションを開き、質問で分類。終了の記録はなし：回数を数え、時間は測らない。"},
        "tm.solo_digitos": {"es": "En esta pasada solo valen {digitos}: las fases.", "en": "In this pass only {digitos} count: the phases.", "fr": "Dans cette passe seuls {digitos} comptent : les phases.", "pt": "Nesta passagem só valem {digitos}: as fases.", "it": "In questa passata valgono solo {digitos}: le fasi.", "ja": "このパスで使えるのは {digitos} のフェーズだけです。"},
        "tm.sin_fases_tt": {"es": "En este análisis no hay fases: solo la acción y las preguntas. El tiempo-movimiento sale del análisis completo.", "en": "This analysis has no phases: only the action and the questions. Time-motion comes from the complete analysis.", "fr": "Cette analyse n'a pas de phases : seulement l'action et les questions. Le temps-mouvement vient de l'analyse complète.", "pt": "Nesta análise não há fases: só a ação e as perguntas. O tempo-movimento sai da análise completa.", "it": "Questa analisi non ha fasi: solo l'azione e le domande. Il tempo-movimento viene dall'analisi completa.", "ja": "この分析にフェーズはありません：アクションと質問だけです。タイムモーションは完全分析から。"},
        "tm.pasada_acciones": {"es": "Está en la pasada de acciones: [F3] pasa a las fases para marcarlas.", "en": "You are in the action pass: [F3] switches to the phases to mark them.", "fr": "Vous êtes dans la passe des actions : [F3] passe aux phases pour les marquer.", "pt": "Está na passagem de ações: [F3] passa às fases para as marcar.", "it": "Sei nella passata delle azioni: [F3] passa alle fasi per segnarle.", "ja": "アクションのパスにいます：[F3] でフェーズに切り替えて記録。"},
        "tm.anterior_empieza": {"es": "La fase anterior ({fase}) empieza en {reloj}: avance el vídeo, o retírela con {retirar}.", "en": "The previous phase ({fase}) starts at {reloj}: move the video forward, or remove it with {retirar}.", "fr": "La phase précédente ({fase}) commence à {reloj} : avancez la vidéo, ou retirez-la avec {retirar}.", "pt": "A fase anterior ({fase}) começa em {reloj}: avance o vídeo, ou retire-a com {retirar}.", "it": "La fase precedente ({fase}) inizia a {reloj}: avanza il video, o toglila con {retirar}.", "ja": "前のフェーズ（{fase}）は {reloj} から：動画を進めるか、{retirar} で取り消してください。"},
        "tm.ya_esta": {"es": "Ya está en {fase}: nada que marcar.", "en": "Already in {fase}: nothing to mark.", "fr": "Déjà en {fase} : rien à marquer.", "pt": "Já está em {fase}: nada a marcar.", "it": "Già in {fase}: niente da segnare.", "ja": "すでに {fase} です：記録するものはありません。"},
        "tm.marcada": {"es": "#{n}  {fase} desde {reloj}  —  la próxima tecla la cierra", "en": "#{n}  {fase} from {reloj}  —  the next key closes it", "fr": "#{n}  {fase} depuis {reloj}  —  la prochaine touche la ferme", "pt": "#{n}  {fase} desde {reloj}  —  a próxima tecla fecha-a", "it": "#{n}  {fase} da {reloj}  —  il prossimo tasto la chiude", "ja": "#{n}  {fase} {reloj} から — 次のキーで閉じます"},
        "tm.nada_que_retirar": {"es": "No hay ninguna fase que retirar.", "en": "No phase to remove.", "fr": "Aucune phase à retirer.", "pt": "Não há nenhuma fase para retirar.", "it": "Nessuna fase da togliere.", "ja": "取り消すフェーズがありません。"},
        "tm.evento_sin_fin": {"es": "En este análisis la acción es un evento: no hay fin que marcar. [I] o un número abre la siguiente.", "en": "In this analysis the action is an event: there is no end to mark. [I] or a number opens the next one.", "fr": "Dans cette analyse l'action est un événement : pas de fin à marquer. [I] ou un chiffre ouvre la suivante.", "pt": "Nesta análise a ação é um evento: não há fim a marcar. [I] ou um número abre a próxima.", "it": "In questa analisi l'azione è un evento: nessuna fine da segnare. [I] o un numero apre la prossima.", "ja": "この分析ではアクションはイベントです：終了の記録はありません。[I] か数字で次を開きます。"},
        "tm.teclas_eventos": {"es": "[I] o un número: la acción y las preguntas · sin fin que marcar", "en": "[I] or a number: the action and the questions · no end to mark", "fr": "[I] ou un chiffre : l'action et les questions · pas de fin à marquer", "pt": "[I] ou um número: a ação e as perguntas · sem fim a marcar", "it": "[I] o un numero: l'azione e le domande · nessuna fine da segnare", "ja": "[I] か数字：アクションと質問 · 終了の記録なし"},
        "tm.pista_eventos": {"es": "[I] o un número para la siguiente acción", "en": "[I] or a number for the next action", "fr": "[I] ou un chiffre pour l'action suivante", "pt": "[I] ou um número para a próxima ação", "it": "[I] o un numero per la prossima azione", "ja": "次のアクションは [I] か数字"},

        "hub.load_folder": {"es": "Abrir carpeta", "en": "Open folder", "fr": "Ouvrir un dossier", "pt": "Abrir pasta", "it": "Apri cartella", "ja": "フォルダを開く"},
        "hub.export_dataset": {
            "es": "Exportar Dataset", "en": "Export Dataset",
            "fr": "Exporter le Dataset", "pt": "Tudo",
            "it": "Esporta Dataset", "ja": "データセットをエクスポート",
        },
        "hub.export_selected": {
            "es": "Exportar Seleccionados", "en": "Export Selected",
            "fr": "Exporter la Sélection", "pt": "Selecionados",
            "it": "Esporta Selezionati", "ja": "選択をエクスポート",
        },
        "hub.search_placeholder": {"es": "Buscar", "en": "Search", "fr": "Rechercher", "pt": "Buscar", "it": "Cerca", "ja": "検索"},
        "hub.empty_heading": {"es": "Ninguna carpeta abierta", "en": "No folder open", "fr": "Aucun dossier ouvert", "pt": "Nenhuma pasta aberta", "it": "Nessuna cartella aperta", "ja": "フォルダが開かれていません"},
        "hub.empty_hint": {"es": "Abre una carpeta con vídeos, o arrástrala aquí.", "en": "Open a folder with videos, or drop it here.", "fr": "Ouvrez un dossier de vidéos, ou déposez-le ici.", "pt": "Abra uma pasta com vídeos, ou arraste-a para aqui.", "it": "Apri una cartella con video, o trascinala qui.", "ja": "動画のあるフォルダを開くか、ここにドロップしてください。"},
        "hub.empty_formats": {"es": ".mp4 · .avi · .mov · .mkv", "en": ".mp4 · .avi · .mov · .mkv", "fr": ".mp4 · .avi · .mov · .mkv", "pt": ".mp4 · .avi · .mov · .mkv", "it": ".mp4 · .avi · .mov · .mkv", "ja": ".mp4 · .avi · .mov · .mkv"},
        "hub.no_recent": {
            "es": "Sin carpetas recientes",
            "en": "No recent folders",
            "fr": "Aucun dossier récent",
            "pt": "Nenhuma pasta recente",
            "it": "Nessuna cartella recente",
            "ja": "最近のフォルダはありません",
        },
        "hub.clear_recent": {
            "es": "Limpiar Recientes",
            "en": "Clear Recent",
            "fr": "Effacer les Récents",
            "pt": "Limpar Recentes",
            "it": "Cancella Recenti",
            "ja": "最近をクリア",
        },
        # ── Hub columns ──────────────────────────────────────
        "hub.col_id": {"es": "#", "en": "#", "fr": "#", "pt": "#", "it": "#", "ja": "#"},
        "hub.col_video": {
            "es": "COMBATE",
            "en": "BOUT",
            "fr": "COMBAT",
            "pt": "COMBATE",
            "it": "INCONTRO",
            "ja": "試合",
        },
        "hub.col_athletes": {
            "es": "ATLETAS", "en": "ATHLETES", "fr": "ATHLÈTES",
            "pt": "ATLETAS", "it": "ATLETI", "ja": "選手",
        },
        "hub.col_category": {
            "es": "CATEGORÍA", "en": "CATEGORY", "fr": "CATÉGORIE",
            "pt": "CATEGORIA", "it": "CATEGORIA", "ja": "カテゴリ",
        },
        # ── «Não identificável»: por qué no se identifica ──────
        # Son del programa, no del karate (decisión 0004): los usa
        # models/no_identificable.py. El resto del árbol de preguntas
        # es del karate y está en karlos_karate/textos.py.
        "video.asalto": {
            "es": "Asalto {n} de {total}", "en": "Round {n} of {total}",
            "fr": "Round {n} sur {total}", "pt": "Assalto {n} de {total}",
            "it": "Round {n} di {total}", "ja": "ラウンド {n}/{total}"},
        "tree.m_arbitro": {"es": "El árbitro se interpone", "pt": "O árbitro interpõe-se",
            "en": "The referee blocks the view", "fr": "The referee blocks the view",
            "it": "The referee blocks the view", "ja": "The referee blocks the view"},
        "tree.m_fuera": {"es": "Atleta fuera del encuadre", "pt": "Atleta fora do enquadramento",
            "en": "Athlete outside the frame", "fr": "Athlete outside the frame",
            "it": "Athlete outside the frame", "ja": "Athlete outside the frame"},
        "tree.m_tapado": {"es": "Tapado por el otro atleta", "pt": "Tapado pelo outro atleta",
            "en": "Hidden by the other athlete", "fr": "Hidden by the other athlete",
            "it": "Hidden by the other athlete", "ja": "Hidden by the other athlete"},
        "tree.m_corte": {"es": "Corte de plano o repetición", "pt": "Corte de plano ou repetição",
            "en": "Camera cut or replay", "fr": "Camera cut or replay",
            "it": "Camera cut or replay", "ja": "Camera cut or replay"},
        "tree.m_rapido": {"es": "Demasiado rápido o desenfocado", "pt": "Demasiado rápido ou desfocado",
            "en": "Too fast or blurred", "fr": "Too fast or blurred",
            "it": "Too fast or blurred", "ja": "Too fast or blurred"},
        "tree.m_video": {"es": "Fallo del vídeo (corrupto, saltos o congelado)",
            "pt": "Falha do vídeo (corrompido, saltos ou congelado)",
            "en": "Video fault (corrupt, dropped frames or frozen)",
            "fr": "Video fault (corrupt, dropped frames or frozen)",
            "it": "Video fault (corrupt, dropped frames or frozen)",
            "ja": "Video fault (corrupt, dropped frames or frozen)"},
        "tree.m_otro": {"es": "Otro motivo (escribirlo)", "pt": "Outro motivo (escrever)",
            "en": "Another reason (write it)", "fr": "Another reason (write it)",
            "it": "Another reason (write it)", "ja": "Another reason (write it)"},

        "hub.col_duration": {
            "es": "DURACIÓN", "en": "DURATION", "fr": "DURÉE",
            "pt": "DURAÇÃO", "it": "DURATA", "ja": "時間",
        },
        "hub.col_annotations": {
            "es": "ANOT.", "en": "ANNOT.", "fr": "ANNOT.",
            "pt": "ANOTAÇÕES", "it": "ANNOT.", "ja": "注釈",
        },
        "hub.col_score": {
            "es": "PUNTOS", "en": "SCORE", "fr": "SCORE",
            "pt": "PONTOS", "it": "PUNTEGGIO", "ja": "スコア",
        },
        "hub.col_status": {
            "es": "ESTADO", "en": "STATUS", "fr": "STATUT",
            "pt": "ESTADO", "it": "STATO", "ja": "状態",
        },
        "hub.col_actions": {
            "es": "ACCIONES", "en": "ACTIONS", "fr": "ACTIONS",
            "pt": "AÇÕES", "it": "AZIONI", "ja": "操作",
        },
        # ── Hub statuses ─────────────────────────────────────
        "hub.status_all": {"es": "Todas", "en": "All", "fr": "Toutes", "pt": "Todas", "it": "Tutte", "ja": "すべて"},
        "hub.status_pending": {
            "es": "Pendiente", "en": "Pending", "fr": "En attente",
            "pt": "Pendente", "it": "In Attesa", "ja": "保留",
        },
        "hub.status_in_progress": {
            "es": "En Progreso", "en": "In Progress",
            "fr": "En cours", "pt": "Em progresso", "it": "In Corso", "ja": "進行中",
        },
        "hub.status_completed": {
            "es": "Completado", "en": "Completed",
            "fr": "Terminé", "pt": "Concluído", "it": "Completato", "ja": "完了",
        },
        # ── Hub context menu ────────────────────────────────
        "hub.ctx_open": {"es": "Abrir Anotador", "en": "Open Annotator", "fr": "Ouvrir l'Annotateur", "pt": "Abrir combate", "it": "Apri Annotatore", "ja": "アノテーターを開く"},
        "hub.ctx_report": {"es": "Ver Reporte", "en": "View Report", "fr": "Voir le Rapport", "pt": "Ver relatório", "it": "Vedi Report", "ja": "レポートを見る"},
        "hub.round_active": {"es": "Pasada", "en": "Pass", "fr": "Passe", "pt": "Avaliação", "it": "Passaggio", "ja": "パス"},
        "hub.round_new": {"es": "Nueva pasada de evaluación", "en": "New evaluation pass", "fr": "Nouvelle passe", "pt": "Nova passagem de avaliação", "it": "Nuovo passaggio", "ja": "新しい評価パス"},
        "hub.round_manage": {"es": "Gestionar pasadas — renombrar o eliminar", "en": "Manage passes — rename or delete", "fr": "Gérer les passes", "pt": "Gerir passagens — renomear ou eliminar", "it": "Gestisci passaggi", "ja": "パスの管理"},
        "hub.export": {"es": "Exportar", "en": "Export", "fr": "Exporter", "pt": "Exportar", "it": "Esporta", "ja": "エクスポート"},
        "hub.ctx_bout_info": {"es": "Datos del combate…", "en": "Bout info…", "fr": "Infos du combat…", "pt": "Dados do combate…", "it": "Dati dell'incontro…", "ja": "試合情報…"},
        "hub.ctx_compare": {"es": "Comparar evaluadores…", "en": "Compare evaluators…", "fr": "Comparer les évaluateurs…", "pt": "Comparar avaliadores…", "it": "Confronta valutatori…", "ja": "評価者を比較…"},
        "hub.ctx_mark_done": {"es": "Marcar como concluido", "en": "Mark as done", "fr": "Marquer comme terminé", "pt": "Marcar como concluído", "it": "Segna come completato", "ja": "完了としてマーク"},
        "hub.ctx_unmark_done": {"es": "Quitar la marca de concluido", "en": "Unmark as done", "fr": "Retirer la marque de terminé", "pt": "Desmarcar como concluído", "it": "Rimuovi completato", "ja": "完了マークを外す"},
        "hub.ctx_clear_annotations": {"es": "Borrar todas las anotaciones…", "en": "Clear all annotations…", "fr": "Effacer toutes les annotations…", "pt": "Apagar todas as anotações…", "it": "Cancella tutte le annotazioni…", "ja": "すべての注釈を削除…"},
        "hub.ctx_remove": {"es": "Eliminar Sesión", "en": "Remove Session", "fr": "Supprimer la Session", "pt": "Remover da lista", "it": "Rimuovi Sessione", "ja": "セッションを削除"},
        # ── Hub tooltips ────────────────────────────────────
        "hub.tt_report": {"es": "Ver Reporte", "en": "View Report", "fr": "Voir le Rapport", "pt": "Ver relatório", "it": "Vedi Report", "ja": "レポートを見る"},
        "hub.tt_open": {"es": "Abrir Anotador", "en": "Open Annotator", "fr": "Ouvrir l'Annotateur", "pt": "Abrir", "it": "Apri Annotatore", "ja": "アノテーターを開く"},
        "ws.tech_dock": {"es": "Técnicas", "en": "Techniques", "fr": "Techniques", "pt": "Técnicas", "it": "Tecniche", "ja": "技術"},
        "ws.ann_log": {"es": "Registro de Anotaciones", "en": "Annotation Log", "fr": "Journal d'Annotations", "pt": "Registro de Anotações", "it": "Registro Annotazioni", "ja": "注釈ログ"},
        # ── Status bar messages ─────────────────────────────
        "stat.ready": {"es": "Listo — presiona [F] para iniciar pelea, [I] para marcar START", "en": "Ready — press [F] to start fight, [I] to mark START", "fr": "Prêt — appuyez sur [F] pour commencer, [I] pour marquer DÉBUT", "pt": "Pronto — pressione [F] para iniciar, [I] para marcar INÍCIO", "it": "Pronto — premi [F] per iniziare, [I] per marcare INIZIO", "ja": "準備完了 — [F]で試合開始、[I]で開始をマーク"},
        "stat.fight_active": {"es": "Pelea en curso — presiona [G] para finalizar", "en": "Fight in progress — press [G] to end", "fr": "Combat en cours — appuyez sur [G] pour terminer", "pt": "Luta em andamento — pressione [G] para finalizar", "it": "Combattimento in corso — premi [G] per terminare", "ja": "試合中 — [G]で終了"},
        "stat.start_marked": {"es": "START marcado — selecciona técnica, [O] para END", "en": "START marked — select technique, [O] to END", "fr": "DÉBUT marqué — sélectionnez une technique, [O] pour FIN", "pt": "INÍCIO marcado — selecione técnica, [O] para FIM", "it": "INIZIO marcato — seleziona tecnica, [O] per FINE", "ja": "開始マーク済み — 技術を選択、[O]で終了"},
        "stat.tech_selected": {"es": "Técnica seleccionada — presiona [O] para marcar END", "en": "Technique selected — press [O] to mark END", "fr": "Technique sélectionnée — appuyez sur [O] pour marquer FIN", "pt": "Técnica selecionada — pressione [O] para marcar FIM", "it": "Tecnica selezionata — premi [O] per marcare FINE", "ja": "技術選択済み — [O]で終了をマーク"},
        "stat.no_videos": {"es": "No se encontraron videos (.mp4, .avi, .mov, .mkv) en la carpeta seleccionada.", "en": "No video files found (.mp4, .avi, .mov, .mkv) in the selected folder.", "fr": "Aucun fichier vidéo trouvé (.mp4, .avi, .mov, .mkv) dans le dossier sélectionné.", "pt": "Nenhum arquivo de vídeo encontrado (.mp4, .avi, .mov, .mkv) na pasta selecionada.", "it": "Nessun file video trovato (.mp4, .avi, .mov, .mkv) nella cartella selezionata.", "ja": "選択されたフォルダに動画ファイル(.mp4, .avi, .mov, .mkv)が見つかりません。"},
        "stat.loaded": {"es": "Cargados {total} videos ({new} nuevos, {all} total)", "en": "Loaded {total} videos ({new} new, {all} total)", "fr": "{total} vidéos chargées ({new} nouvelles, {all} au total)", "pt": "Carregados {total} vídeos ({new} novos, {all} total)", "it": "Caricati {total} video ({new} nuovi, {all} totali)", "ja": "{total}本の動画を読み込みました（{new}本新規、合計{all}本）"},
        "stat.focus_mode": {"es": "Modo Concentración — Ctrl+Shift+F para salir", "en": "Focus Mode — Ctrl+Shift+F to exit", "fr": "Mode Concentration — Ctrl+Shift+F pour quitter", "pt": "Modo Concentração — Ctrl+Shift+F para sair", "it": "Modalità Concentrazione — Ctrl+Shift+F per uscire", "ja": "フォーカスモード — Ctrl+Shift+Fで終了"},
        "stat.focus_off": {"es": "Modo Concentración desactivado", "en": "Focus Mode disabled", "fr": "Mode Concentration désactivé", "pt": "Modo Concentração desativado", "it": "Modalità Concentrazione disattivata", "ja": "フォーカスモード解除"},
        "stat.session_restored": {"es": "Sesión restaurada — {n} anotaciones · {athlete}", "en": "Session restored — {n} annotations · {athlete}", "fr": "Session restaurée — {n} annotations · {athlete}", "pt": "Sessão restaurada — {n} anotações · {athlete}", "it": "Sessione ripristinata — {n} annotazioni · {athlete}", "ja": "セッション復元 — {n}件の注釈 · {athlete}"},
        "stat.new_session": {"es": "Sesión nueva — {label} — pulsa [F] para marcar el inicio del combate", "en": "New session — {label} — press [F] to mark Fight Start", "fr": "Nouvelle session — {label} — appuyez sur [F] pour le début", "pt": "Sessão nova — {label} — pressione [F] para marcar o início da luta", "it": "Nuova sessione — {label} — premi [F] per l'inizio", "ja": "新規セッション — {label} — [F]で試合開始"},
        "stat.active_session": {"es": "Sesión activa: {name} — presiona [F] para marcar Fight Start", "en": "Active session: {name} — press [F] to mark Fight Start", "fr": "Session active : {name} — appuyez sur [F] pour marquer le début", "pt": "Sessão ativa: {name} — pressione [F] para marcar Início da Luta", "it": "Sessione attiva: {name} — premi [F] per marcare Inizio Combattimento", "ja": "アクティブセッション: {name} — [F]で試合開始をマーク"},
        "stat.session_done": {"es": "Sesión completada. Listo para ver reporte, exportar o editar.", "en": "Session completed. Ready to view report, export, or edit.", "fr": "Session terminée. Prêt à voir le rapport, exporter ou modifier.", "pt": "Sessão concluída. Pronto para ver relatório, exportar ou editar.", "it": "Sessione completata. Pronto per visualizzare il report, esportare o modificare.", "ja": "セッション完了。レポート表示、エクスポート、編集が可能です。"},
        "stat.batch_export": {"es": "Exportación por lote: {n}/{total} sesiones exportadas a {folder}", "en": "Batch export: {n}/{total} sessions exported to {folder}", "fr": "Export par lot : {n}/{total} sessions exportées vers {folder}", "pt": "Exportação em lote: {n}/{total} sessões exportadas para {folder}", "it": "Esportazione batch: {n}/{total} sessioni esportate in {folder}", "ja": "バッチエクスポート: {n}/{total}セッションを{folder}にエクスポート"},
        # ── Other ───────────────────────────────────────────
        "dialog.no_videos": {"es": "Sin Videos", "en": "No Videos", "fr": "Aucune Vidéo", "pt": "Sem Vídeos", "it": "Nessun Video", "ja": "動画なし"},
        "dialog.video_error": {"es": "Error de Video", "en": "Video Error", "fr": "Erreur Vidéo", "pt": "Erro de Vídeo", "it": "Errore Video", "ja": "動画エラー"},
        "dialog.load_error": {"es": "Error al Cargar", "en": "Load Error", "fr": "Erreur de Chargement", "pt": "Erro ao Carregar", "it": "Errore di Caricamento", "ja": "読み込みエラー"},
        "dialog.file_error": {"es": "Error de Archivo", "en": "File Error", "fr": "Erreur de Fichier", "pt": "Erro de Arquivo", "it": "Errore File", "ja": "ファイルエラー"},
        "dialog.export_failed": {"es": "Error al Exportar", "en": "Export Failed", "fr": "Échec de l'Export", "pt": "Falha na Exportação", "it": "Esportazione Fallita", "ja": "エクスポート失敗"},
        "dialog.export_complete": {"es": "Exportación Completa", "en": "Export Complete", "fr": "Export Terminé", "pt": "Exportação Concluída", "it": "Esportazione Completa", "ja": "エクスポート完了"},
        "dialog.export_force_title": {"es": "Validación Falló — ¿Forzar Exportación?", "en": "Validation Failed — Force Export?", "fr": "Échec de Validation — Forcer l'Export ?", "pt": "Falha na Validação — Forçar Exportação?", "it": "Validazione Fallita — Forzare l'Esportazione?", "ja": "検証失敗 — 強制エクスポートしますか？"},
        "dialog.export_force_question": {"es": "¿Exportar de todas formas? El Excel se generará igualmente y los problemas quedarán listados en la hoja 'Validation Warnings'.", "en": "Export anyway? The Excel file will still be generated and every issue will be listed in the 'Validation Warnings' sheet.", "fr": "Exporter quand même ? Le fichier Excel sera généré et chaque problème sera listé dans la feuille 'Validation Warnings'.", "pt": "Exportar mesmo assim? O Excel será gerado e os problemas ficarão listados na aba 'Validation Warnings'.", "it": "Esportare comunque? Il file Excel verrà generato e i problemi saranno elencati nel foglio 'Validation Warnings'.", "ja": "強制的にエクスポートしますか？Excelは生成され、問題は'Validation Warnings'シートに記載されます。"},
        "dialog.export_forced_note": {"es": "Exportación forzada completada. Revisa la hoja 'Validation Warnings' del Excel para ver los problemas detectados.", "en": "Forced export complete. Check the 'Validation Warnings' sheet in the Excel file for the detected issues.", "fr": "Export forcé terminé. Consultez la feuille 'Validation Warnings' du fichier Excel pour voir les problèmes détectés.", "pt": "Exportação forçada concluída. Verifique a aba 'Validation Warnings' do Excel para ver os problemas detectados.", "it": "Esportazione forzata completata. Controlla il foglio 'Validation Warnings' del file Excel per i problemi rilevati.", "ja": "強制エクスポート完了。検出された問題はExcelの'Validation Warnings'シートを確認してください。"},
        "dialog.export_file_locked": {"es": "No se pudo guardar el archivo. Si está abierto en Excel, ciérralo e inténtalo de nuevo.", "en": "Could not save the file. If it is open in Excel, close it and try again.", "fr": "Impossible d'enregistrer le fichier. S'il est ouvert dans Excel, fermez-le et réessayez.", "pt": "Não foi possível salvar o arquivo. Se estiver aberto no Excel, feche-o e tente novamente.", "it": "Impossibile salvare il file. Se è aperto in Excel, chiudilo e riprova.", "ja": "ファイルを保存できませんでした。Excelで開いている場合は閉じてから再試行してください。"},
        "dialog.nothing_export": {"es": "Nada que Exportar", "en": "Nothing to Export", "fr": "Rien à Exporter", "pt": "Nada para Exportar", "it": "Niente da Esportare", "ja": "エクスポートするものがありません"},
        "dialog.not_completed": {"es": "No Completado", "en": "Not Completed", "fr": "Non Terminé", "pt": "Não Concluído", "it": "Non Completato", "ja": "未完了"},
        "dialog.not_completed_msg": {"es": "Esta sesión aún no ha sido completamente analizada.\nCompleta ambos pases de atleta antes de ver el reporte.", "en": "This session has not been fully analyzed yet.\nComplete both athlete passes before viewing the report.", "fr": "Cette session n'a pas encore été entièrement analysée.\nTerminez les deux passes d'athlète avant de voir le rapport.", "pt": "Esta sessão ainda não foi totalmente analisada.\nComplete ambas as passagens de atleta antes de ver o relatório.", "it": "Questa sessione non è stata ancora completamente analizzata.\nCompleta entrambi i passaggi atleta prima di visualizzare il report.", "ja": "このセッションはまだ完全に分析されていません。\nレポートを表示する前に両方の選手パスを完了してください。"},
        "menu.view": {"es": "&Ver", "en": "&View", "fr": "&Affichage", "pt": "&Ver", "it": "&Visualizza", "ja": "表示(&V)"},
        "menu.language": {"es": "Idioma", "en": "Language", "fr": "Langue", "pt": "Idioma", "it": "Lingua", "ja": "言語"},
        "menu.reset_layout": {"es": "Restablecer Diseño", "en": "Reset Layout", "fr": "Réinitialiser la Disposition", "pt": "Redefinir Layout", "it": "Ripristina Layout", "ja": "レイアウトをリセット"},
        "wf.start": {"es": "START en frame {frame} — selecciona técnica", "en": "START at frame {frame} — select technique", "fr": "DÉBUT à l'image {frame} — sélectionnez une technique", "pt": "INÍCIO no frame {frame} — selecione técnica", "ja": "フレーム{frame}で開始 — 技術を選択"},
        # ── Bout Info popup ─────────────────────────────────
        "bout.title": {"es": "Información del Combate", "en": "Bout Information", "fr": "Information du Combat", "pt": "Informação do Combate", "it": "Informazioni Combattimento", "ja": "試合情報"},
        "bout.window_title": {"es": "Información del Combate", "en": "Bout Information", "fr": "Information du Combat", "pt": "Informação do Combate", "it": "Informazioni Combattimento", "ja": "試合情報"},
        "bout.subtitle": {"es": "Registro Elite de Combate", "en": "Elite Combat Registry", "fr": "Registre de Combat Élite", "pt": "Registro de Combate Elite", "it": "Registro Combattimento Elite", "ja": "エリート戦闘記録"},
        "bout.event_details": {"es": "DETALLES DEL EVENTO", "en": "EVENT DETAILS", "fr": "DÉTAILS DE L'ÉVÉNEMENT", "pt": "DETALHES DO EVENTO", "it": "DETTAGLI EVENTO", "ja": "イベント詳細"},
        "bout.fight_setup": {"es": "CONFIGURACIÓN DEL COMBATE", "en": "FIGHT SETUP", "fr": "CONFIGURATION DU COMBAT", "pt": "CONFIGURAÇÃO DA LUTA", "it": "IMPOSTAZIONE COMBATTIMENTO", "ja": "試合設定"},
        "bout.evaluator": {"es": "EVALUADOR", "en": "EVALUATOR", "fr": "ÉVALUATEUR", "pt": "AVALIADOR", "it": "VALUTATORE", "ja": "評価者"},
        "bout.competition_name": {"es": "Nombre de la Competencia", "en": "Competition Name", "fr": "Nom de la Compétition", "pt": "Nome da Competição", "it": "Nome Competizione", "ja": "大会名"},
        "bout.event_phase": {"es": "Fase del Evento", "en": "Event Phase", "fr": "Phase de l'Événement", "pt": "Fase do Evento", "it": "Fase Evento", "ja": "イベントフェーズ"},
        "bout.category_type": {"es": "Tipo de Categoría", "en": "Category Type", "fr": "Type de Catégorie", "pt": "Tipo de Categoria", "it": "Tipo Categoria", "ja": "カテゴリタイプ"},
        "bout.weight_category": {"es": "Categoría de Peso", "en": "Weight Category", "fr": "Catégorie de Poids", "pt": "Categoria de Peso", "it": "Categoria Peso", "ja": "体重別階級"},
        "bout.pool": {"es": "Grupo / Pool", "en": "Pool / Group", "fr": "Poule / Groupe", "pt": "Grupo / Chave", "it": "Girone / Gruppo", "ja": "プール / グループ"},
        "bout.tatami": {"es": "Tatami", "en": "Tatami", "fr": "Tatami", "pt": "Tatami", "it": "Tatami", "ja": "畳"},
        "bout.athlete_name": {"es": "Nombre del Atleta", "en": "Athlete Name", "fr": "Nom de l'Athlète", "pt": "Nome do Atleta", "it": "Nome Atleta", "ja": "選手名"},
        "bout.country": {"es": "País", "en": "Country", "fr": "Pays", "pt": "País", "it": "Paese", "ja": "国"},
        "bout.result": {"es": "Resultado", "en": "Result", "fr": "Résultat", "pt": "Resultado", "it": "Risultato", "ja": "結果"},
        "bout.winner": {"es": "Ganador", "en": "Winner", "fr": "Vainqueur", "pt": "Vencedor", "it": "Vincitore", "ja": "勝者"},
        "bout.decision": {"es": "Decisión", "en": "Decision", "fr": "Décision", "pt": "Decisão", "it": "Decisione", "ja": "決定"},
        "bout.guard": {"es": "Guardia", "en": "Guard", "fr": "Garde", "pt": "Guarda", "it": "Guardia", "ja": "構え"},
        "bout.club": {"es": "Club / Dojo", "en": "Club / Dojo", "fr": "Club / Dojo", "pt": "Clube / Dojo", "it": "Club / Dojo", "ja": "クラブ / 道場"},
        "bout.bout_number": {"es": "Combate #", "en": "Bout #", "fr": "Combat #", "pt": "Combate #", "it": "Combattimento #", "ja": "試合 #"},
        "bout.round": {"es": "Ronda", "en": "Round", "fr": "Tour", "pt": "Rodada", "it": "Round", "ja": "ラウンド"},
        "bout.evaluator_name": {"es": "Nombre del Evaluador", "en": "Evaluator Name", "fr": "Nom de l'Évaluateur", "pt": "Nome do Avaliador", "it": "Nome Valutatore", "ja": "評価者名"},
        "bout.institution": {"es": "Institución / Rol", "en": "Institution / Role", "fr": "Institution / Rôle", "pt": "Instituição / Função", "it": "Istituzione / Ruolo", "ja": "機関 / 役割"},
        "bout.analysis_date": {"es": "Fecha de Análisis", "en": "Analysis Date", "fr": "Date d'Analyse", "pt": "Data da Análise", "it": "Data Analisi", "ja": "分析日"},
        "bout.select": {"es": "— Seleccionar —", "en": "— Select —", "fr": "— Sélectionner —", "pt": "— Selecionar —", "it": "— Seleziona —", "ja": "— 選択 —"},
        "bout.placeholder": {"es": "—", "en": "—", "fr": "—", "pt": "—", "it": "—", "ja": "—"},
        "bout.cancel": {"es": "Cancelar", "en": "Cancel", "fr": "Annuler", "pt": "Cancelar", "it": "Annulla", "ja": "キャンセル"},
        "bout.save": {"es": "Guardar Metadatos", "en": "Save Metadata", "fr": "Enregistrer Métadonnées", "pt": "Salvar Metadados", "it": "Salva Metadati", "ja": "メタデータを保存"},
        # ── Video panel ─────────────────────────────────────
        "video.open_prompt": {"es": "Abrir un video para comenzar", "en": "Open a video to begin", "fr": "Ouvrir une vidéo pour commencer", "pt": "Abrir um vídeo para começar", "it": "Apri un video per iniziare", "ja": "ビデオを開いて開始"},
        "video.play": {"es": "Reproducir", "en": "Play", "fr": "Lecture", "pt": "Reproduzir", "it": "Riproduci", "ja": "再生"},
        "video.pause": {"es": "Pausar", "en": "Pause", "fr": "Pause", "pt": "Pausar", "it": "Pausa", "ja": "一時停止"},
        "video.play_pause": {"es": "Reproducir/Pausar", "en": "Play/Pause", "fr": "Lecture/Pause", "pt": "Reproduzir/Pausar", "it": "Riproduci/Pausa", "ja": "再生/一時停止"},
        "video.volume": {"es": "Volumen", "en": "Volume", "fr": "Volume", "pt": "Volume", "it": "Volume", "ja": "音量"},
        "video.mute": {"es": "Silenciar / activar sonido", "en": "Mute / unmute", "fr": "Couper / activer le son", "pt": "Silenciar / ativar som", "it": "Disattiva / attiva audio", "ja": "ミュート切替"},
        "video.fight_start": {"es": "Inicio Combate [F]", "en": "Fight START [F]", "fr": "Début Combat [F]", "pt": "Início Luta [F]", "it": "Inizio Combatt. [F]", "ja": "試合開始 [F]"},
        "video.fight_end": {"es": "Fin Combate [G]", "en": "Fight END [G]", "fr": "Fin Combat [G]", "pt": "Fim Luta [G]", "it": "Fine Combatt. [G]", "ja": "試合終了 [G]"},
        "video.mark_start": {"es": "INICIO [I]", "en": "START [I]", "fr": "DÉBUT [I]", "pt": "INÍCIO [I]", "it": "INIZIO [I]", "ja": "開始 [I]"},
        "video.mark_end": {"es": "FIN [O]", "en": "END [O]", "fr": "FIN [O]", "pt": "FIM [O]", "it": "FINE [O]", "ja": "終了 [O]"},
        "video.live_stats": {"es": "{a}: {aka} pts  |  {b}: {ao} pts  |  Total: {total}  |  Transcurrido: {elapsed}s", "en": "{a}: {aka} pts  |  {b}: {ao} pts  |  Total: {total}  |  Elapsed: {elapsed}s", "fr": "{a}: {aka} pts  |  {b}: {ao} pts  |  Total: {total}  |  Écoulé: {elapsed}s", "pt": "{a}: {aka} pts  |  {b}: {ao} pts  |  Total: {total}  |  Decorrido: {elapsed}s", "it": "{a}: {aka} pts  |  {b}: {ao} pts  |  Totale: {total}  |  Trascorso: {elapsed}s", "ja": "{a}: {aka}点  |  {b}: {ao}点  |  合計: {total}  |  経過: {elapsed}秒"},
        "video.pass_label": {"es": "PASE {pass_num}/2 — {athlete}", "en": "PASS {pass_num}/2 — {athlete}", "fr": "PASSE {pass_num}/2 — {athlete}", "pt": "PASSE {pass_num}/2 — {athlete}", "it": "PASSAGGIO {pass_num}/2 — {athlete}", "ja": "パス {pass_num}/2 — {athlete}"},
        # ── Fight End popup ────────────────────────────────
        "fightend.title": {"es": "Combate Finalizado", "en": "Fight End Registered", "fr": "Fin de Combat Enregistrée", "pt": "Fim da Luta Registrado", "it": "Fine Combattimento Registrata", "ja": "試合終了登録"},
        "fightend.heading": {"es": "Segmento de Combate Grabado", "en": "Fight Segment Recorded", "fr": "Segment de Combat Enregistré", "pt": "Segmento de Luta Gravado", "it": "Segmento Combattimento Registrato", "ja": "試合セグメント記録"},
        "fightend.subtitle": {"es": "Segmento grabado exitosamente.", "en": "Segment recorded successfully.", "fr": "Segment enregistré avec succès.", "pt": "Segmento gravado com sucesso.", "it": "Segmento registrato con successo.", "ja": "セグメントが正常に記録されました。"},
        "fightend.fight_start": {"es": "Inicio del Combate", "en": "Fight Start", "fr": "Début du Combat", "pt": "Início da Luta", "it": "Inizio Combattimento", "ja": "試合開始"},
        "fightend.fight_end": {"es": "Fin del Combate", "en": "Fight End", "fr": "Fin du Combat", "pt": "Fim da Luta", "it": "Fine Combattimento", "ja": "試合終了"},
        "fightend.duration": {"es": "Duración", "en": "Duration", "fr": "Durée", "pt": "Duração", "it": "Durata", "ja": "時間"},
        "fightend.frame": {"es": "Frame {frame}", "en": "Frame {frame}", "fr": "Image {frame}", "pt": "Frame {frame}", "it": "Fotogramma {frame}", "ja": "フレーム {frame}"},
        "fightend.annotations": {"es": "{count} anotaciones", "en": "{count} annotations", "fr": "{count} annotations", "pt": "{count} anotações", "it": "{count} annotazioni", "ja": "{count}件の注釈"},
        "fightend.not_analyzed": {"es": "Aún no analizado", "en": "Not analyzed yet", "fr": "Pas encore analysé", "pt": "Ainda não analisado", "it": "Non ancora analizzato", "ja": "未分析"},
        "fightend.total": {"es": "Total", "en": "Total", "fr": "Total", "pt": "Total", "it": "Totale", "ja": "合計"},
        "fightend.records": {"es": "{count} registros", "en": "{count} records", "fr": "{count} enregistrements", "pt": "{count} registros", "it": "{count} record", "ja": "{count}件の記録"},
        "fightend.next_fight": {"es": "SIGUIENTE COMBATE", "en": "NEXT FIGHT", "fr": "COMBAT SUIVANT", "pt": "PRÓXIMA LUTA", "it": "PROSSIMO COMBATTIMENTO", "ja": "次の試合"},
        "fightend.next_fight_desc": {"es": "Iniciar un nuevo segmento de combate en el mismo video", "en": "Start a new fight segment on the same video", "fr": "Démarrer un nouveau segment de combat sur la même vidéo", "pt": "Iniciar um novo segmento de luta no mesmo vídeo", "it": "Avvia un nuovo segmento di combattimento sullo stesso video", "ja": "同じ動画で新しい試合セグメントを開始"},
        "fightend.finish_export_desc": {"es": "Cerrar, marcar como Completado y volver al Hub", "en": "Close, mark as Completed and return to Hub", "fr": "Fermer, marquer comme Terminé et retourner au Hub", "pt": "Fechar, marcar como Concluído e voltar ao Hub", "it": "Chiudi, segna come Completato e torna all'Hub", "ja": "閉じて完了マークを付け、ハブに戻る"},
        "fightend.analyze": {"es": "ANALIZAR {athlete}", "en": "ANALYZE {athlete}", "fr": "ANALYSER {athlete}", "pt": "ANALISAR {athlete}", "it": "ANALIZZA {athlete}", "ja": "{athlete}を分析"},
        "fightend.analyze_desc": {"es": "Rebobinar video y cambiar al otro atleta", "en": "Rewind video and switch to the other athlete", "fr": "Rembobiner la vidéo et passer à l'autre athlète", "pt": "Rebobinar vídeo e mudar para o outro atleta", "it": "Riavvolgi video e passa all'altro atleta", "ja": "動画を巻き戻してもう一方の選手に切り替え"},
        "fightend.continue": {"es": "CONTINUAR ACTUAL", "en": "CONTINUE CURRENT", "fr": "CONTINUER ACTUEL", "pt": "CONTINUAR ATUAL", "it": "CONTINUA CORRENTE", "ja": "現在を続行"},
        "fightend.continue_desc": {"es": "Seguir anotando al atleta actual", "en": "Keep annotating current athlete", "fr": "Continuer à annoter l'athlète actuel", "pt": "Continuar anotando o atleta atual", "it": "Continua ad annotare l'atleta corrente", "ja": "現在の選手の注釈を続ける"},
        "toolbar.bout_info": {"es": "Info Combate", "en": "Bout Info", "fr": "Info Combat", "pt": "Dados do combate", "it": "Info Combattimento", "ja": "試合情報"},
        "toolbar.view_report": {"es": "Ver Reporte", "en": "View Report", "fr": "Voir Rapport", "pt": "Ver relatório", "it": "Vedi Report", "ja": "レポート表示"},
        # ── Detail popup ────────────────────────────────────
        "detail.target_level": {"es": "Nivel objetivo:", "en": "Target Level:", "fr": "Niveau cible:", "pt": "Nível alvo:", "it": "Livello target:", "ja": "目標レベル:"},
        "detail.scoring_outcome": {"es": "Resultado de puntuación:", "en": "Scoring Outcome:", "fr": "Résultat du score:", "pt": "Resultado da pontuação:", "it": "Esito punteggio:", "ja": "採点結果:"},
        "detail.confirm": {"es": "Confirmar [Enter]", "en": "Confirm [Enter]", "fr": "Confirmer [Entrée]", "pt": "Confirmar [Enter]", "it": "Conferma [Invio]", "ja": "確認 [Enter]"},
        # ── Referee stop popup ──────────────────────────────
        "refstop.title": {"es": "Parada del Árbitro — Tipo", "en": "Referee Stop — Type", "fr": "Arrêt Arbitre — Type", "pt": "Parada do Árbitro — Tipo", "it": "Stop Arbitro — Tipo", "ja": "レフェリーストップ — タイプ"},
        "refstop.select_reason": {"es": "Seleccionar motivo de parada:", "en": "Select stop reason:", "fr": "Sélectionner le motif d'arrêt:", "pt": "Selecionar motivo da parada:", "it": "Seleziona motivo stop:", "ja": "停止理由を選択:"},
        "refstop.cancel": {"es": "Cancelar [Esc]", "en": "Cancel [Esc]", "fr": "Annuler [Échap]", "pt": "Cancelar [Esc]", "it": "Annulla [Esc]", "ja": "キャンセル [Esc]"},
        # ── Main window / workspace ─────────────────────────
        "ws.back_btn": {"es": "←  Hub", "en": "←  Hub", "fr": "←  Hub", "pt": "←  Hub", "it": "←  Hub", "ja": "←  Hub"},
        "ws.workflow_hint": {"es": "Flujo: [I] INICIO -> clic técnica (nivel + puntuación) -> [O] FIN", "en": "Workflow: [I] START -> click technique (level + score) -> [O] END", "fr": "Workflow: [I] DÉBUT -> clic technique (niveau + score) -> [O] FIN", "pt": "Fluxo: [I] INÍCIO -> clique técnica (nível + pontuação) -> [O] FIM", "it": "Flusso: [I] INIZIO -> clic tecnica (livello + punteggio) -> [O] FINE", "ja": "ワークフロー: [I] 開始 -> 技術クリック (レベル+スコア) -> [O] 終了"},
        "dialog.no_sessions": {"es": "Sin Sesiones", "en": "No Sessions", "fr": "Aucune Session", "pt": "Sem Sessões", "it": "Nessuna Sessione", "ja": "セッションなし"},
        # ── La pantalla de inicio (decisión 0006, F5.3d) ─────
        # El deporte, en una línea: el paquete trae la suya («Kumite ·
        # reglamento WKF 2026»); sin ella, su nombre.
        "deporte.descripcion": {
            "es": "{deporte}", "en": "{deporte}", "fr": "{deporte}",
            "pt": "{deporte}", "it": "{deporte}", "ja": "{deporte}",
        },
        "inicio.version": {
            "es": "versión {version}", "en": "version {version}",
            "fr": "version {version}", "pt": "versão {version}",
            "it": "versione {version}", "ja": "バージョン {version}",
        },
        # ── Qué se analiza (después del asistido, donde hay tiempo-movimiento) ──
        "analisis.pregunta": {
            "es": "¿Qué se analiza?", "en": "What do you analyse?", "fr": "Qu'analysez-vous ?",
            "pt": "O que se analisa?", "it": "Cosa si analizza?", "ja": "何を分析しますか？"},
        "analisis.tt": {
            "es": "Técnico-táctico", "en": "Technical-tactical", "fr": "Technico-tactique",
            "pt": "Técnico-tática", "it": "Tecnico-tattica", "ja": "技術・戦術"},
        "analisis.tt_sub": {
            "es": "Cada acción, con sus preguntas.", "en": "Every action, with its questions.",
            "fr": "Chaque action, avec ses questions.", "pt": "Cada ação, com as suas perguntas.",
            "it": "Ogni azione, con le sue domande.", "ja": "各アクションを質問で記録。"},
        "analisis.tm": {
            "es": "Tiempo-movimiento", "en": "Time-motion", "fr": "Temps-mouvement",
            "pt": "Tempo-movimento", "it": "Tempo-movimento", "ja": "タイムモーション"},
        "analisis.tm_sub": {
            "es": "Solo las fases del combate. Sin preguntas.", "en": "Only the phases of the bout. No questions.",
            "fr": "Seulement les phases du combat. Sans questions.", "pt": "Só as fases do combate. Sem perguntas.",
            "it": "Solo le fasi dell'incontro. Senza domande.", "ja": "試合のフェーズのみ。質問なし。"},
        # «Integrado» y no «completo» (Johan, 19-10-2026): es el análisis
        # conjunto de tiempo-movimiento y técnico-táctico a partir del mismo
        # registro (Tabben et al. 2015; Miarka et al. 2014). El código
        # interno sigue diciendo «complete»: así se guarda en disco.
        "analisis.completo": {
            "es": "Integrado", "en": "Integrated", "fr": "Intégrée",
            "pt": "Integrada", "it": "Integrata", "ja": "統合"},
        "analisis.completo_sub": {
            "es": "Tiempo-movimiento y técnico-táctico del mismo registro.", "en": "Time-motion and technical-tactical from one record.",
            "fr": "Temps-mouvement et technico-tactique d'un même registre.", "pt": "Tempo-movimento e técnico-tática do mesmo registo.",
            "it": "Tempo-movimento e tecnico-tattica dallo stesso registro.", "ja": "同じ記録からタイムモーションと技術・戦術。"},
        # ── El registro breve: como estaba (el karate no cambia); un deporte
        # puede traer los suyos en sus textos.
        "log.titulo": {"es": "ANNOTATION LOG", "en": "ANNOTATION LOG", "fr": "ANNOTATION LOG",
                       "pt": "ANNOTATION LOG", "it": "ANNOTATION LOG", "ja": "ANNOTATION LOG"},
        # ── El panel de preguntas ──
        "guia.accion": {
            "es": "acción", "en": "action", "fr": "action", "pt": "ação", "it": "azione", "ja": "アクション"},
        "guia.paso": {
            "es": "{cabecera} · paso {n} de {total}", "en": "{cabecera} · step {n} of {total}",
            "fr": "{cabecera} · étape {n} sur {total}", "pt": "{cabecera} · passo {n} de {total}",
            "it": "{cabecera} · passo {n} di {total}", "ja": "{cabecera} · {n}/{total}"},
        "guia.retroceso": {
            "es": "[retroceso] deshacer la última respuesta", "en": "[backspace] undo the last answer",
            "fr": "[retour arrière] annuler la dernière réponse", "pt": "[retrocesso] desfaz a última resposta",
            "it": "[backspace] annulla l'ultima risposta", "ja": "[Backspace] 直前の回答を取り消す"},
        # Desde el 16-10-2026 el diálogo es la primera pantalla del
        # programa: sin padre no hay adonde volver y el botón cierra.
        "analisis.salir": {"es": "Salir", "en": "Quit", "fr": "Quitter",
                           "pt": "Sair", "it": "Esci", "ja": "終了"},
        "analisis.voltar": {
            "es": "‹ Volver", "en": "‹ Back", "fr": "‹ Retour",
            "pt": "‹ Voltar", "it": "‹ Indietro", "ja": "‹ 戻る"},
        "analisis.inicio": {
            "es": "‹ Inicio", "en": "‹ Home", "fr": "‹ Accueil",
            "pt": "‹ Início", "it": "‹ Inizio", "ja": "‹ 最初へ"},
        "analisis.inicio_tip": {
            "es": "Volver a la pantalla inicial para elegir otro análisis. Cada análisis guarda sus propias anotaciones.",
            "en": "Back to the start screen to choose another analysis. Each analysis keeps its own annotations.",
            "fr": "Revenir à l'écran d'accueil pour choisir une autre analyse. Chaque analyse garde ses propres annotations.",
            "pt": "Voltar ao ecrã inicial para escolher outra análise. Cada análise guarda as suas próprias anotações.",
            "it": "Tornare alla schermata iniziale per scegliere un'altra analisi. Ogni analisi conserva le proprie annotazioni.",
            "ja": "最初の画面に戻って別の分析を選びます。各分析は独自の注釈を保存します。"},
        "analisis.cuaderno": {"es": "Ahora: {nome}. Cada análisis guarda sus propias anotaciones.", "en": "Now: {nome}. Each analysis keeps its own annotations.", "fr": "Maintenant : {nome}. Chaque analyse garde ses propres annotations.", "pt": "Agora: {nome}. Cada análise guarda as suas próprias anotações.", "it": "Ora: {nome}. Ogni analisi conserva le proprie annotazioni.", "ja": "現在:{nome}。各分析は独自の注釈を保存します。"},
        "analisis.entrar": {
            "es": "Continuar", "en": "Continue", "fr": "Continuer",
            "pt": "Continuar", "it": "Continua", "ja": "続ける"},
        # ── Welcome Screen ──────────────────────────────────
        "welcome.subtitle": {
            "es": "Plataforma de Análisis de Deportes de Combate",
            "en": "Combat Sports Analysis Platform",
            "fr": "Plateforme d'Analyse des Sports de Combat",
            "pt": "Plataforma de Análise de Esportes de Combate",
            "it": "Piattaforma di Analisi per Sport da Combattimento",
            "ja": "格闘技分析プラットフォーム",
        },
        "welcome.version": {
            "es": "Versión 1.0", "en": "Version 1.0",
            "fr": "Version 1.0", "pt": "Versão 1.0",
            "it": "Versione 1.0", "ja": "バージョン 1.0",
        },
        "welcome.new_session": {
            "es": "NUEVA SESIÓN", "en": "NEW SESSION",
            "fr": "NOUVELLE SESSION", "pt": "NOVA SESSÃO",
            "it": "NUOVA SESSIONE", "ja": "新規セッション",
        },
        "welcome.new_session_desc": {
            "es": "Empezar a anotar\nun nuevo video",
            "en": "Start annotating\na new video",
            "fr": "Commencer à annoter\nune nouvelle vidéo",
            "pt": "Começar a anotar\num novo vídeo",
            "it": "Inizia ad annotare\nun nuovo video",
            "ja": "新しい動画の\n注釈を開始",
        },
        "welcome.load_session": {
            "es": "CARGAR SESIÓN", "en": "LOAD SESSION",
            "fr": "CHARGER SESSION", "pt": "CARREGAR SESSÃO",
            "it": "CARICA SESSIONE", "ja": "セッションを読み込む",
        },
        "welcome.load_session_desc": {
            "es": "Continuar trabajo\nanterior",
            "en": "Continue previous\nwork",
            "fr": "Continuer le travail\nprécédent",
            "pt": "Continuar trabalho\nanterior",
            "it": "Continua il lavoro\nprecedente",
            "ja": "以前の作業を\n続ける",
        },
        "welcome.recent_sessions": {
            "es": "SESIONES RECIENTES", "en": "RECENT SESSIONS",
            "fr": "SESSIONS RÉCENTES", "pt": "SESSÕES RECENTES",
            "it": "SESSIONI RECENTI", "ja": "最近のセッション",
        },
        "welcome.settings": {
            "es": "Ajustes", "en": "Settings",
            "fr": "Paramètres", "pt": "Configurações",
            "it": "Impostazioni", "ja": "設定",
        },
        "welcome.help": {
            "es": "Ayuda", "en": "Help",
            "fr": "Aide", "pt": "Ajuda",
            "it": "Aiuto", "ja": "ヘルプ",
        },
        # ── Edit Annotation ─────────────────────────────────
        "edit.title": {
            "es": "Editar Anotación — {technique}", "en": "Edit Annotation — {technique}",
            "fr": "Modifier l'Annotation — {technique}", "pt": "Editar Anotação — {technique}",
            "it": "Modifica Annotazione — {technique}", "ja": "注釈を編集 — {technique}",
        },
        "edit.header": {
            "es": "Editando: {technique} [{athlete}]", "en": "Editing: {technique} [{athlete}]",
            "fr": "Modification : {technique} [{athlete}]", "pt": "Editando: {technique} [{athlete}]",
            "it": "Modifica: {technique} [{athlete}]", "ja": "編集: {technique} [{athlete}]",
        },
        "edit.athlete": {
            "es": "Atleta:", "en": "Athlete:",
            "fr": "Athlète :", "pt": "Atleta:",
            "it": "Atleta:", "ja": "選手:",
        },
        "edit.category": {
            "es": "Categoría:", "en": "Category:",
            "fr": "Catégorie :", "pt": "Categoria:",
            "it": "Categoria:", "ja": "カテゴリ:",
        },
        "edit.subcategory": {
            "es": "Subcategoría:", "en": "Subcategory:",
            "fr": "Sous-catégorie :", "pt": "Subcategoria:",
            "it": "Sottocategoria:", "ja": "サブカテゴリ:",
        },
        "edit.technique": {
            "es": "Técnica:", "en": "Technique:",
            "fr": "Technique :", "pt": "Técnica:",
            "it": "Tecnica:", "ja": "技術:",
        },
        "edit.level": {
            "es": "Nivel:", "en": "Level:",
            "fr": "Niveau :", "pt": "Nível:",
            "it": "Livello:", "ja": "レベル:",
        },
        "edit.stance": {
            "es": "Posición:", "en": "Stance:",
            "fr": "Position :", "pt": "Postura:",
            "it": "Posizione:", "ja": "構え:",
        },
        "edit.target": {
            "es": "Objetivo:", "en": "Target:",
            "fr": "Cible :", "pt": "Alvo:",
            "it": "Bersaglio:", "ja": "ターゲット:",
        },
        "edit.score": {
            "es": "Puntuación:", "en": "Score:",
            "fr": "Score :", "pt": "Pontuação:",
            "it": "Punteggio:", "ja": "スコア:",
        },
        "edit.frame_start": {
            "es": "Frame Inicio:", "en": "Frame Start:",
            "fr": "Image Début :", "pt": "Frame Início:",
            "it": "Fotogramma Inizio:", "ja": "開始フレーム:",
        },
        "edit.frame_end": {
            "es": "Frame Fin:", "en": "Frame End:",
            "fr": "Image Fin :", "pt": "Frame Fim:",
            "it": "Fotogramma Fine:", "ja": "終了フレーム:",
        },
        "edit.notes": {
            "es": "Notas:", "en": "Notes:",
            "fr": "Notes :", "pt": "Notas:",
            "it": "Note:", "ja": "メモ:",
        },
        "edit.cancel": {
            "es": "Cancelar", "en": "Cancel",
            "fr": "Annuler", "pt": "Cancelar",
            "it": "Annulla", "ja": "キャンセル",
        },
        "edit.save_changes": {
            "es": "Guardar Cambios", "en": "Save Changes",
            "fr": "Enregistrer les Modifications", "pt": "Salvar Alterações",
            "it": "Salva Modifiche", "ja": "変更を保存",
        },
        # ── Session Wizard ──────────────────────────────────
        "wizard.title": {
            "es": "Nueva Sesión", "en": "New Session",
            "fr": "Nouvelle Session", "pt": "Nova Sessão",
            "it": "Nuova Sessione", "ja": "新規セッション",
        },
        "wizard.back": {
            "es": "← Atrás", "en": "← Back",
            "fr": "← Retour", "pt": "← Voltar",
            "it": "← Indietro", "ja": "← 戻る",
        },
        "wizard.step": {
            "es": "PASO {current} DE {total}", "en": "STEP {current} OF {total}",
            "fr": "ÉTAPE {current} SUR {total}", "pt": "PASSO {current} DE {total}",
            "it": "PASSAGGIO {current} DI {total}", "ja": "ステップ {current}/{total}",
        },
        "wizard.cancel": {
            "es": "Cancelar", "en": "Cancel",
            "fr": "Annuler", "pt": "Cancelar",
            "it": "Annulla", "ja": "キャンセル",
        },
        "wizard.skip": {
            "es": "Saltar", "en": "Skip",
            "fr": "Passer", "pt": "Pular",
            "it": "Salta", "ja": "スキップ",
        },
        "wizard.next": {
            "es": "Siguiente →", "en": "Next →",
            "fr": "Suivant →", "pt": "Próximo →",
            "it": "Avanti →", "ja": "次へ →",
        },
        "wizard.start": {
            "es": "INICIAR ANÁLISIS", "en": "START ANALYSIS",
            "fr": "COMMENCER L'ANALYSE", "pt": "INICIAR ANÁLISE",
            "it": "AVVIA ANALISI", "ja": "分析を開始",
        },
    }
