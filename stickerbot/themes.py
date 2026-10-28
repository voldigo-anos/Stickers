"""Creation de themes Telegram (.attheme) a partir d'une photo.

Les couleurs du theme (fond, ecritures, bulles, vocaux, icones...) sont
extraites de la photo, et la photo elle-meme est embarquee comme fond
d'ecran du theme. Le fichier .attheme est destine a Telegram Android.
"""

import colorsys
import logging
from io import BytesIO

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

WALLPAPER_MAX_SIDE = 1080
WALLPAPER_JPEG_QUALITY = 85


# --------------------------------------------------------------------------
# extraction des couleurs de la photo
# --------------------------------------------------------------------------

def _luminance(rgb):
    r, g, b = (c / 255 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _saturation(rgb):
    r, g, b = (c / 255 for c in rgb)
    return colorsys.rgb_to_hls(r, g, b)[2]


def _clamp(v):
    return max(0, min(255, int(round(v))))


def _mix(a, b, t):
    """melange deux couleurs : t=0 -> a, t=1 -> b"""
    return tuple(_clamp(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _shift(rgb, amount):
    """eclaircit (amount>0) ou assombrit (amount<0)"""
    target = (255, 255, 255) if amount > 0 else (0, 0, 0)
    return _mix(rgb, target, abs(amount))


def extract_palette(data: bytes):
    """renvoie les couleurs de base du theme a partir de la photo"""
    im = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert('RGB')
    small = im.resize((64, 64), Image.LANCZOS)
    # regroupe les couleurs proches pour trouver les dominantes
    quant = small.quantize(colors=6, method=Image.MEDIANCUT).convert('RGB')
    counts = sorted(quant.getcolors(64 * 64), reverse=True)
    colors = [rgb for _, rgb in counts]

    avg = tuple(sum(count * rgb[i] for count, rgb in counts) // (64 * 64) for i in range(3))

    # accent = la couleur la plus vive de la photo
    accent = max(colors, key=lambda c: _saturation(c) * (0.4 + _luminance(c)))
    if _saturation(accent) < 0.08:
        # photo terne : on utilise la couleur moyenne comme accent
        accent = avg

    # fond = couleur dominante tiree vers le sombre ou le clair
    dominant = colors[0]
    dark_theme = _luminance(avg) < 0.45
    if dark_theme:
        background = _shift(dominant, -0.55)
        background2 = _shift(dominant, -0.35)
    else:
        # Do not wash colorful photos out into a nearly white interface.
        background = _shift(dominant, 0.18)
        background2 = _shift(dominant, 0.30)

    # ecriture lisible sur le fond
    text = (255, 255, 255) if _luminance(background) < 0.5 else (20, 20, 20)
    text_soft = _mix(text, background, 0.35)

    # couleurs propres aux discussions : la photo y sert de fond, donc les
    # bulles sont translucides et les ecritures suivent les teintes de la photo
    chat_dark = _luminance(avg) < 0.6
    in_bg = _shift(dominant, -0.62) if chat_dark else _shift(dominant, 0.80)
    out_bg = _shift(accent, 0.72) if chat_dark else _shift(accent, -0.55)
    in_text = _mix((255, 255, 255), accent, 0.08) if _luminance(in_bg) < 0.5 else _shift(accent, -0.85)
    out_text = _mix((255, 255, 255), accent, 0.08) if _luminance(out_bg) < 0.5 else _shift(accent, -0.85)
    chat = {
        'in_bg': in_bg,
        'out_bg': out_bg,
        'in_text': in_text,
        'in_soft': _mix(in_text, in_bg, 0.3),
        'in_accent': _shift(accent, 0.45) if _luminance(in_bg) < 0.5 else _shift(accent, -0.45),
        'out_text': out_text,
        'out_soft': _mix(out_text, out_bg, 0.3),
    }

    return {
        'chat': chat,
        'accent': accent,
        'background': background,
        'background2': background2,
        'text': text,
        'text_soft': text_soft,
        'dark': dark_theme,
    }


# --------------------------------------------------------------------------
# generation du fichier .attheme
# --------------------------------------------------------------------------

def _argb(rgb, alpha=255):
    """couleur -> entier signe 32 bits (format attendu par .attheme)"""
    value = (alpha << 24) | (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]
    return value - 0x100000000 if value >= 0x80000000 else value


def _theme_keys(p):
    """construit le dictionnaire cle=couleur du theme"""
    accent, bg, bg2 = p['accent'], p['background'], p['background2']
    text, soft = p['text'], p['text_soft']
    bubble_in = bg2
    bubble_out = _mix(accent, bg, 0.35)
    out_text = text if _luminance(bubble_out) < 0.55 else (20, 20, 20)

    keys = {
        'chat_wallpaper': bg,
        # fonds et textes de la liste des discussions
        'dialogBackground': bg,
        'dialogBackgroundGray': bg2,
        'dialogTextBlack': text,
        'dialogTextLink': accent,
        'dialogTextBlue': accent,
        'dialogTextBlue2': accent,
        'dialogTextBlue4': accent,
        'dialogTextGray': soft,
        'dialogTextGray2': soft,
        'dialogInputField': soft,
        'dialogInputFieldActivated': accent,
        'dialogCheckboxSquareBackground': accent,
        'dialogCheckboxSquareCheck': bg,
        'dialogCheckboxSquareUnchecked': soft,
        'dialogCheckboxSquareDisabled': soft,
        'dialogScrollGlow': bg,
        'dialogRoundCheckBox': accent,
        'dialogRoundCheckBoxCheck': bg,
        'dialogRadioBackground': soft,
        'dialogRadioBackgroundChecked': accent,
        'dialogLineProgress': accent,
        'dialogLineProgressBackground': soft,
        'dialogButton': accent,
        'dialogButtonSelector': _mix(accent, bg, 0.5),
        'dialogIcon': soft,
        'dialogGrayLine': soft,
        'dialogSearchBackground': bg2,
        'dialogSearchHint': soft,
        'dialogSearchIcon': soft,
        'dialogSearchText': text,
        'dialogFloatingButton': accent,
        'dialogFloatingButtonPressed': accent,
        'dialogFloatingIcon': bg,
        'dialogShadowLine': bg2,
        'dialogBadgeBackground': accent,
        'dialogBadgeText': bg,
        'dialogMutedIcon': soft,
        'dialogOnlineBadge': accent,
        'dialogName': text,
        'dialogMessage': soft,
        'dialogMessageWithMedia': text,
        'dialogSendingText': soft,
        'dialogSentTime': soft,
        'dialogUnreadBadge': accent,
        'dialogUnreadBadgeText': bg,
        'dialogTypingText': accent,

        # fenetre principale
        'windowBackgroundWhite': bg,
        'windowBackgroundUnchecked': bg2,
        'windowBackgroundChecked': accent,
        'windowBackgroundCheckText': text,
        'progressCircle': accent,
        'listSelectorSDK21': _mix(accent, bg, 0.7),
        'windowBackgroundWhiteGrayIcon': soft,
        'windowBackgroundWhiteBlueText': accent,
        'windowBackgroundWhiteBlueText3': accent,
        'windowBackgroundWhiteBlueText4': accent,
        'windowBackgroundWhiteBlueText6': soft,
        'windowBackgroundWhiteBlueText7': soft,
        'windowBackgroundWhiteGreenText2': accent,
        'windowBackgroundWhiteGrayText': soft,
        'windowBackgroundWhiteGrayText2': soft,
        'windowBackgroundWhiteGrayText3': soft,
        'windowBackgroundWhiteGrayText4': soft,
        'windowBackgroundWhiteGrayText8': soft,
        'windowBackgroundWhiteBlackText': text,
        'windowBackgroundWhiteValueText': accent,
        'windowBackgroundWhiteLinkText': accent,
        'windowBackgroundWhiteBlueHeader': accent,
        'windowBackgroundWhiteInputField': bg2,
        'windowBackgroundWhiteInputFieldActivated': accent,

        # interrupteurs / cases
        'switchTrack': soft,
        'switchTrackChecked': accent,
        'switch2Track': soft,
        'switch2TrackChecked': accent,
        'checkboxSquareBackground': accent,
        'checkboxSquareCheck': bg,
        'checkboxSquareUnchecked': soft,
        'checkboxSquareDisabled': soft,

        # conversation (bulles, ecritures, vocaux, liens)
        'chat_inBubble': bubble_in,
        'chat_inBubbleSelected': _mix(bubble_in, accent, 0.25),
        'chat_inBubbleShadow': bg2,
        'chat_outBubble': bubble_out,
        'chat_outBubbleSelected': _mix(bubble_out, accent, 0.25),
        'chat_outBubbleShadow': bg2,
        'chat_messageTextIn': text,
        'chat_messageTextOut': out_text,
        'chat_messageLinkIn': accent,
        'chat_messageLinkOut': out_text,
        'chat_inSentTime': soft,
        'chat_outSentTime': _mix(out_text, bubble_out, 0.4),
        'chat_inSentTimeSelected': soft,
        'chat_outSentTimeSelected': _mix(out_text, bubble_out, 0.3),
        'chat_inSentClock': soft,
        'chat_outSentClock': _mix(out_text, bubble_out, 0.3),
        'chat_inViews': soft,
        'chat_outViews': _mix(out_text, bubble_out, 0.4),
        'chat_inReplyNameText': accent,
        'chat_outReplyNameText': out_text,
        'chat_inReplyLine': accent,
        'chat_outReplyLine': out_text,
        'chat_inReplyMessageText': soft,
        'chat_outReplyMessageText': _mix(out_text, bubble_out, 0.3),
        'chat_inForwardedNameText': accent,
        'chat_outForwardedNameText': out_text,
        'chat_inViaBotNameText': accent,
        'chat_outViaBotNameText': out_text,
        'chat_inFileNameText': accent,
        'chat_outFileNameText': out_text,
        'chat_inFileInfoText': soft,
        'chat_outFileInfoText': _mix(out_text, bubble_out, 0.4),
        'chat_inFileIcon': soft,
        'chat_outFileIcon': _mix(out_text, bubble_out, 0.4),
        'chat_inFileBackground': bubble_in,
        'chat_outFileBackground': bubble_out,
        'chat_inContactNameText': accent,
        'chat_outContactNameText': out_text,
        'chat_inContactPhoneText': soft,
        'chat_outContactPhoneText': _mix(out_text, bubble_out, 0.3),
        'chat_inContactIcon': soft,
        'chat_outContactIcon': _mix(out_text, bubble_out, 0.4),
        'chat_inLocationIcon': soft,
        'chat_outLocationIcon': _mix(out_text, bubble_out, 0.4),
        'chat_inSiteNameText': accent,
        'chat_outSiteNameText': out_text,
        'chat_inInstant': accent,
        'chat_outInstant': out_text,
        'chat_inInstantSelected': accent,
        'chat_outInstantSelected': out_text,
        'chat_inLoader': accent,
        'chat_outLoader': out_text,
        'chat_inMediaIcon': text,
        'chat_outMediaIcon': out_text,
        'chat_inMediaIconSelected': text,
        'chat_outMediaIconSelected': out_text,
        'chat_inMenu': soft,
        'chat_outMenu': _mix(out_text, bubble_out, 0.4),
        'chat_inTime': soft,
        'chat_outTime': _mix(out_text, bubble_out, 0.4),

        # messages vocaux (forme d'onde)
        'chat_inVoiceSeekbar': accent,
        'chat_inVoiceSeekbarFill': accent,
        'chat_inVoiceSeekbarSelected': accent,
        'chat_outVoiceSeekbar': _mix(out_text, bubble_out, 0.5),
        'chat_outVoiceSeekbarFill': out_text,
        'chat_outVoiceSeekbarSelected': out_text,
        'chat_inAudioProgress': accent,
        'chat_outAudioProgress': out_text,
        'chat_inAudioSelectedProgress': accent,
        'chat_outAudioSelectedProgress': out_text,
        'chat_inAudioPerfomerText': soft,
        'chat_outAudioPerfomerText': _mix(out_text, bubble_out, 0.3),
        'chat_inAudioTitleText': text,
        'chat_outAudioTitleText': out_text,
        'chat_inAudioDurationText': soft,
        'chat_outAudioDurationText': _mix(out_text, bubble_out, 0.4),
        'chat_inAudioDurationSelectedText': soft,
        'chat_outAudioDurationSelectedText': _mix(out_text, bubble_out, 0.3),
        'chat_inAudioSeekbar': soft,
        'chat_outAudioSeekbar': _mix(out_text, bubble_out, 0.5),
        'chat_inAudioSeekbarFill': accent,
        'chat_outAudioSeekbarFill': out_text,
        'chat_inAudioSeekbarSelected': accent,
        'chat_outAudioSeekbarSelected': out_text,
        'chat_inAudioCacheSeekbar': soft,
        'chat_outAudioCacheSeekbar': _mix(out_text, bubble_out, 0.5),

        # barres et boutons de la conversation
        'chat_messagePanelBackground': bg2,
        'chat_messagePanelText': text,
        'chat_messagePanelHint': soft,
        'chat_messagePanelIcons': soft,
        'chat_messagePanelVoiceBackground': accent,
        'chat_messagePanelVoicePressed': accent,
        'chat_messagePanelVoiceShadow': bg,
        'chat_messagePanelSend': accent,
        'chat_messagePanelSendShadow': bg,
        'chat_messagePanelVoiceLock': accent,
        'chat_messagePanelVoiceLockBackground': bg2,
        'chat_messagePanelVoiceDelete': soft,
        'chat_messagePanelReplyBackground': bg2,
        'chat_messagePanelReplyLine': accent,
        'chat_messagePanelReplyNameText': accent,
        'chat_messagePanelReplyMessageText': soft,
        'chat_messagePanelReplyIcon': accent,
        'chat_messagePanelCancelSending': soft,
        'chat_messagePanelVideoFrame': accent,
        'chat_messagePanelVideoProgress': accent,
        'chat_messagePanelVoiceDuration': text,
        'chat_recordedVoicePlayPause': bg,
        'chat_recordedVoicePlayPausePressed': bg,
        'chat_recordedVoiceDot': accent,
        'chat_recordedVoiceBackground': bg2,
        'chat_recordedVoiceProgress': accent,
        'chat_recordedVoiceProgressInner': bg,
        'chat_recordTime': text,
        'chat_emojiPanelBackground': bg2,
        'chat_emojiPanelBadgeBackground': accent,
        'chat_emojiPanelBadgeText': bg,
        'chat_emojiPanelIcon': soft,
        'chat_emojiPanelIconSelected': accent,
        'chat_emojiPanelStickerPackSelector': bg,
        'chat_emojiPanelIconSelector': accent,
        'chat_emojiPanelShadowLine': bg,
        'chat_emojiPanelEmptyText': soft,
        'chat_emojiPanelTrendingTitle': text,
        'chat_emojiPanelTrendingDescription': soft,
        'chat_emojiSearchBackground': bg,
        'chat_emojiSearchIcon': soft,
        'chat_emojiPanelBackspace': soft,
        'chat_emojiPanelMasksIcon': soft,
        'chat_emojiPanelMasksIconSelected': accent,
        'chat_emojiPanelNewTrending': accent,
        'chat_gifSaveHintBackground': bg2,
        'chat_gifSaveHintText': text,
        'chat_goDownButton': bg2,
        'chat_goDownButtonShadow': bg,
        'chat_goDownButtonIcon': soft,
        'chat_goDownButtonCounter': text,
        'chat_goDownButtonCounterBackground': accent,
        'chat_goDownButtonIconCounter': bg,
        'chat_topPanelBackground': bg,
        'chat_topPanelIcon': soft,
        'chat_topPanelClose': soft,
        'chat_topPanelCall': accent,
        'chat_topPanelTitle': text,
        'chat_topPanelMessage': soft,
        'chat_inPollCorrectAnswer': accent,
        'chat_outPollCorrectAnswer': out_text,
        'chat_inPollWrongAnswer': soft,
        'chat_outPollWrongAnswer': _mix(out_text, bubble_out, 0.5),
        'chat_pollTimerBackground': accent,
        'chat_pollTimerIcon': bg,
        'chat_serviceBackground': bg2,
        'chat_serviceBackgroundSelected': _mix(bg2, accent, 0.2),
        'chat_serviceText': text,
        'chat_serviceLink': accent,
        'chat_serviceIcon': text,
        'chat_serviceButton': bg2,
        'chat_serviceButtonText': text,
        'chat_serviceButtonSelector': accent,
        'chat_serviceBotButton': accent,
        'chat_serviceBotButtonText': bg,
        'chat_serviceBotButtonSelector': accent,
        'chat_muteIcon': soft,
        'chat_lockIcon': soft,
        'chat_secretTimeText': soft,
        'chat_secretTimerBackground': bg2,
        'chat_secretTimerText': text,
        'chat_stickerNameText': text,
        'chat_stickerReplyNameText': text,
        'chat_stickerViaBotNameText': text,
        'chat_stickerTimeText': text,
        'chat_stickerSentTimeText': text,
        'chat_textSearchSelection': _mix(accent, bg, 0.5),
        'chat_unreadMessagesStartBackground': accent,
        'chat_unreadMessagesStartText': bg,
        'chat_previewDurationText': text,
        'chat_previewGameText': accent,
        'chat_mediaTimeText': text,
        'chat_mediaInfoBackground': bg2,
        'chat_mediaSentTime': text,
        'chat_mediaViews': text,
        'chat_mediaMenu': text,
        'chat_botButtonText': bg,
        'chat_botKeyboardButtonBackground': bubble_in,
        'chat_botKeyboardButtonBackgroundPressed': accent,
        'chat_botKeyboardButtonText': text,
        'chat_inlineResultIcon': accent,
        'chat_editDoneIcon': accent,
        'chat_addContact': accent,
        'chat_reportSpam': accent,
        'chat_fieldOverlayText': text,
        'chat_attachMediaBanBackground': bg2,
        'chat_attachMediaBanText': text,
        'chat_attachCheckBoxCheck': bg,
        'chat_attachCheckBoxBackground': accent,
        'chat_attachPhotoBackground': bg2,
        'chat_attachCameraIcon1': soft,
        'chat_attachCameraIcon2': soft,
        'chat_attachCameraIcon3': soft,
        'chat_attachCameraIcon4': soft,
        'chat_attachCameraIcon5': soft,
        'chat_attachCameraIcon6': soft,
        'chat_attachHideBackground': bg2,
        'chat_attachHideIcon': text,
        'chat_attachSendBackground': accent,
        'chat_attachSendIcon': bg,
        'chat_attachGalleryBackground': bg2,
        'chat_attachGalleryIcon': text,
        'chat_attachFileBackground': bg2,
        'chat_attachFileIcon': text,
        'chat_attachAudioBackground': bg2,
        'chat_attachAudioIcon': text,
        'chat_attachContactBackground': bg2,
        'chat_attachContactIcon': text,
        'chat_attachLocationBackground': bg2,
        'chat_attachLocationIcon': text,
        'chat_attachPollBackground': bg2,
        'chat_attachPollIcon': text,

        # barre d'action, statut, navigation
        'actionBarDefault': bg,
        'actionBarDefaultIcon': soft,
        'actionBarDefaultTitle': text,
        'actionBarDefaultSubtitle': soft,
        'actionBarDefaultSelector': bg2,
        'actionBarWhiteSelector': bg2,
        'actionBarDefaultSearch': text,
        'actionBarDefaultSearchPlaceholder': soft,
        'actionBarDefaultSubmenuBackground': bg2,
        'actionBarDefaultSubmenuItem': text,
        'actionBarDefaultSubmenuItemIcon': soft,
        'actionBarDefaultArchived': bg,
        'actionBarDefaultArchivedSelector': bg2,
        'actionBarDefaultArchivedIcon': soft,
        'actionBarDefaultArchivedTitle': text,
        'actionBarDefaultArchivedSearch': text,
        'actionBarDefaultArchivedSearchPlaceholder': soft,
        'actionBarTabActiveText': accent,
        'actionBarTabUnactiveText': soft,
        'actionBarTabLine': accent,
        'actionBarTabSelector': bg2,
        'statusBar': bg,
        'navigationBar': bg,
        'divider': bg2,

        # reglages, profil, menus
        'avatar_actionBarSelectorBlue': bg2,
        'avatar_actionBarIconBlue': soft,
        'avatar_subtitleInProfileBlue': soft,
        'avatar_nameInMessageBlue': accent,
        'avatar_backgroundActionBarBlue': bg,
        'avatar_backgroundBlue': bg2,
        'avatar_text': text,
        'avatar_subtitleInProfileCyan': soft,
        'profile_creatorIcon': accent,
        'profile_title': text,
        'profile_actionIcon': soft,
        'profile_actionBackground': bg2,
        'profile_actionPressedBackground': bg,
        'profile_verifiedBackground': accent,
        'profile_verifiedCheck': bg,
        'profile_status': soft,
        'profile_adminIcon': soft,
        'profile_adminIconPressed': accent,
        'key_grayText': soft,
        'key_sheet_scrollUp': soft,
        'key_sheet_other': soft,
        'player_actionBar': bg,
        'player_actionBarSelector': bg2,
        'player_actionBarTitle': text,
        'player_actionBarTop': bg,
        'player_actionBarSubtitle': soft,
        'player_actionBarItems': soft,
        'player_background': bg,
        'player_time': soft,
        'player_progressBackground': bg2,
        'player_progress': accent,
        'player_progressCachedBackground': bg2,
        'player_placeholder': soft,
        'player_placeholderBackground': bg2,
        'player_button': text,
        'player_buttonActive': accent,
        'picker_badge': accent,
        'picker_badgeText': bg,
        'picker_disabledButton': soft,
        'picker_enabledButton': accent,
        'undo_background': bg2,
        'undo_cancelColor': accent,
        'undo_infoColor': text,
        'contextProgressInner1': accent,
        'contextProgressOuter1': bg2,
        'contextProgressInner2': accent,
        'contextProgressOuter2': bg2,
        'contextProgressInner3': accent,
        'contextProgressOuter3': bg2,
        'contextProgressInner4': accent,
        'contextProgressOuter4': bg2,
        'fastScrollActive': accent,
        'fastScrollInactive': soft,
        'fastScrollText': text,
        'featuredStickers_addedIcon': accent,
        'featuredStickers_buttonProgress': bg,
        'featuredStickers_buttonText': bg,
        'groupcreate_hintText': soft,
        'groupcreate_cursor': accent,
        'groupcreate_sectionShadow': bg2,
        'groupcreate_sectionText': text,
        'groupcreate_spanText': text,
        'groupcreate_spanBackground': bg2,
        'groupcreate_checkbox': accent,
        'groupcreate_checkboxCheck': bg,
        'groupcreate_onlineText': accent,
        'groupcreate_offlineText': soft,
        'inappPlayerPerformer': text,
        'inappPlayerTitle': accent,
        'inappPlayerBackground': bg2,
        'inappPlayerPlayPause': accent,
        'inappPlayerClose': soft,
        'returnToCallBackground': accent,
        'returnToCallText': bg,
        'sharedMedia_startStopLoadIcon': accent,
        'sharedMedia_linkPlaceholder': bg2,
        'sharedMedia_linkPlaceholderText': soft,
        'sharedMedia_photoPlaceholder': bg2,
        'sharedMedia_actionMode': bg,
        'voipgroup_actionBar': bg,
        'voipgroup_actionBarItems': soft,
        'voipgroup_actionBarUnscrolled': bg,
        'voipgroup_listViewBackground': bg,
        'voipgroup_windowBackground': bg,
        'voipgroup_inviteMembersBackground': bg2,
        'voipgroup_listAlertText': text,
        'voipgroup_nameText': text,
        'voipgroup_lastSeenText': soft,
        'voipgroup_lastSeenTextUnscrolled': soft,
        'voipgroup_checkText': accent,
        'voipgroup_mutedByAdminIcon': soft,
        'voipgroup_searchBackground': bg2,
        'voipgroup_searchPlaceholder': soft,
        'voipgroup_searchText': text,
        'voipgroup_scrollUp': soft,
        'voipgroup_topPanelBackground': bg2,
        'voipgroup_topPanelBackground1': bg2,
        'voipgroup_topPanelBackground2': bg2,
        'voipgroup_muteButton': accent,
        'voipgroup_muteButton2': accent,
        'voipgroup_muteButton3': accent,
        'voipgroup_unmuteButton': accent,
        'voipgroup_unmuteButton2': accent,
        'voipgroup_connectingProgress': accent,
        'voipgroup_disabledButton': bg2,
        'voipgroup_disabledButtonActive': accent,
        'voipgroup_disabledButtonActiveScrolled': accent,
        'voipgroup_leaveButton': soft,
        'voipgroup_leaveButtonScrolled': soft,
        'voipgroup_leaveCallMenu': soft,
        'voipgroup_listenButton': accent,
        'voipgroup_speakingText': accent,
        'voipgroup_mutedIcon': soft,
        'voipgroup_mutedIconUnscrolled': soft,
        'voipgroup_blueButton': accent,
        'voipgroup_blueButtonText': bg,
        'calls_callReceivedGreenIcon': accent,
        'calls_callReceivedRedIcon': soft,
        'changephoneinfo_image': soft,
        'chats_actionBackground': accent,
        'chats_actionIcon': bg,
        'chats_actionMessage': soft,
        'chats_actionPressedBackground': accent,
        'chats_archiveBackground': bg2,
        'chats_archiveIcon': soft,
        'chats_archivePinBackground': soft,
        'chats_archiveText': text,
        'chats_attachMessage': soft,
        'chats_date': soft,
        'chats_draft': accent,
        'chats_mentionIcon': bg,
        'chats_menuBackground': bg,
        'chats_menuCloud': soft,
        'chats_menuCloudBackgroundCats': bg2,
        'chats_menuItemCheck': accent,
        'chats_menuItemIcon': soft,
        'chats_menuItemText': text,
        'chats_menuPhone': text,
        'chats_menuPhoneCats': soft,
        'chats_menuTopBackgroundCats': bg,
        'chats_message': soft,
        'chats_messageArchived': soft,
        'chats_message_threeLines': soft,
        'chats_muteIcon': soft,
        'chats_name': text,
        'chats_nameArchived': soft,
        'chats_nameIcon': text,
        'chats_nameMessage': text,
        'chats_nameMessageArchived': soft,
        'chats_nameMessageArchived_threeLines': soft,
        'chats_onlineCircle': accent,
        'chats_pinnedIcon': soft,
        'chats_pinnedOverlay': bg2,
        'chats_secretIcon': accent,
        'chats_secretName': accent,
        'chats_sentCheck': accent,
        'chats_sentClock': soft,
        'chats_sentError': soft,
        'chats_sentErrorIcon': soft,
        'chats_sentReadCheck': accent,
        'chats_tabletSelectedOverlay': bg2,
        'chats_unreadCounter': accent,
        'chats_unreadCounterMuted': soft,
        'chats_unreadCounterText': bg,
        'chats_verifiedBackground': accent,
        'chats_verifiedCheck': bg,
        'login_progressInner': bg2,
        'login_progressOuter': accent,
        'musicPicker_badge': accent,
        'musicPicker_badgeText': bg,
        'musicPicker_buttonBackground': accent,
        'musicPicker_buttonIcon': bg,
        'musicPicker_checkbox': accent,
        'musicPicker_checkboxCheck': bg,
        'notificationStripeText': text,
        'notificationStripeBackground': bg2,
        'passport_authorizeBackground': accent,
        'passport_authorizeBackgroundSelected': accent,
        'passport_authorizeText': bg,
        'premiumGradient0': accent,
        'premiumGradient1': _mix(accent, text, 0.3),
        'premiumGradient2': _mix(accent, bg, 0.3),
        'premiumGradientBottomSheet': bg2,
        'premiumSmallBadge': accent,
        'premiumSmallBadgeText': bg,
        'premiumStarGradient1': accent,
        'premiumStarGradient2': _mix(accent, text, 0.3),
        'reactionMentionText': accent,
        'reactionMentionBackground': bg2,
        'reactionMentionButton': accent,
        'reactionMentionButtonText': bg,
        'sendingFileText': soft,
        'sheet_scrollUp': soft,
        'stickers_menu': soft,
        'stickers_menuSelector': bg2,
        'text_RedBold': accent,
        'text_RedRegular': accent,
        'toBeContinuedText': text,
        'wallet_blackText': text,
        'wallet_buttonBackground': accent,
        'wallet_buttonPressedBackground': accent,
        'wallet_buttonText': bg,
        'wallet_commentText': soft,
        'wallet_dateText': soft,
        'wallet_greenText': accent,
        'wallet_releaseBackground': bg2,
        'wallet_rowBackground': bg,
        'wallet_graySettingsText': soft,
        'wallet_whiteText': text,
    }
    keys.pop('chat_wallpaper', None)  # sinon la couleur unie masque la photo
    keys.update(_chat_keys(p, keys, text, soft, accent, out_text))
    return {k: (_argb(*v) if isinstance(v[0], tuple) else _argb(v)) for k, v in keys.items()}


BUBBLE_ALPHA_IN = 0xD3
BUBBLE_ALPHA_OUT = 0xC7
SERVICE_ALPHA = 0x99


def _chat_keys(p, keys, text, soft, accent, out_text_old):
    """recolore les bulles et ecritures des discussions par-dessus la photo"""
    c = p['chat']
    out = {}
    for k, v in keys.items():
        if k.startswith('chat_in') and 'Bubble' not in k:
            if v == text:
                out[k] = c['in_text']
            elif v == accent:
                out[k] = c['in_accent']
            elif v == soft:
                out[k] = c['in_soft']
        elif k.startswith('chat_out') and 'Bubble' not in k and k != 'chat_outFileBackground':
            out[k] = c['out_text'] if v == out_text_old else c['out_soft']
    out.update({
        'chat_inBubble': (c['in_bg'], BUBBLE_ALPHA_IN),
        'chat_inBubbleSelected': (_mix(c['in_bg'], accent, 0.2), 0xE6),
        'chat_inBubbleShadow': (c['in_bg'], 0x33),
        'chat_outBubble': (c['out_bg'], BUBBLE_ALPHA_OUT),
        'chat_outBubbleSelected': (_mix(c['out_bg'], accent, 0.2), 0xE6),
        'chat_outBubbleShadow': (c['out_bg'], 0x33),
        'chat_inFileBackground': c['in_bg'],
        'chat_outFileBackground': c['out_bg'],
        'chat_messageTextIn': c['in_text'],
        'chat_messageTextOut': c['out_text'],
        'chat_messageLinkIn': c['in_accent'],
        'chat_messageLinkOut': c['out_text'],
        'chat_serviceBackground': (c['in_bg'], SERVICE_ALPHA),
        'chat_serviceBackgroundSelected': (c['in_bg'], 0xCC),
        'chat_serviceText': c['in_text'],
        'chat_serviceLink': c['in_accent'],
        'chat_serviceIcon': c['in_text'],
        'chat_serviceButton': (c['in_bg'], SERVICE_ALPHA),
        'chat_serviceButtonText': c['in_text'],
        'chat_botKeyboardButtonBackground': (c['in_bg'], BUBBLE_ALPHA_IN),
        'chat_botKeyboardButtonText': c['in_text'],
        'chat_stickerNameText': c['in_text'],
        'chat_stickerReplyNameText': c['in_text'],
        'chat_stickerViaBotNameText': c['in_text'],
        'chat_stickerTimeText': c['in_text'],
        'chat_stickerSentTimeText': c['in_text'],
        'chat_mediaInfoBackground': (c['in_bg'], SERVICE_ALPHA),
        'chat_goDownButton': (c['in_bg'], BUBBLE_ALPHA_IN),
        'chat_goDownButtonIcon': c['in_text'],
    })
    return out


def _wallpaper_jpeg(data: bytes) -> bytes:
    im = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert('RGB')
    if max(im.width, im.height) > WALLPAPER_MAX_SIDE:
        ratio = WALLPAPER_MAX_SIDE / max(im.width, im.height)
        im = im.resize(
            (max(1, round(im.width * ratio)), max(1, round(im.height * ratio))),
            Image.LANCZOS,
        )
    out = BytesIO()
    im.save(out, 'JPEG', quality=WALLPAPER_JPEG_QUALITY)
    return out.getvalue()


def build_attheme(photo_data: bytes) -> bytes:
    """construit le fichier .attheme complet (couleurs + fond d'ecran)"""
    palette = extract_palette(photo_data)
    keys = _theme_keys(palette)
    wallpaper = _wallpaper_jpeg(photo_data)

    # Telegram Android computes the offset from WPS itself. A numeric
    # wallpaperFileOffset entry alone is ignored/overwritten by its parser.
    text = '\n'.join(f'{k}={v}' for k, v in keys.items()).encode('utf-8')
    return text + b'\nWPS\n' + wallpaper + b'\nWPE\n'
