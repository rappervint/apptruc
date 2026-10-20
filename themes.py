# -*- coding: utf-8 -*-
"""
themes.py - Hệ thống Quản lý Giao diện 12 Tháng & Các Dịp Lễ Hội (Seasonal Themes)
Tự động kích hoạt trước mỗi ngày lễ vài ngày để tạo không khí rộn ràng.
"""

THEMES_CATALOG = {
    # 1. TẾT DƯƠNG LỊCH & CHÀO NĂM MỚI (26/12 - 10/01)
    'new_year': {
        'key': 'new_year',
        'name': 'Chào Năm Mới & Countdown',
        'tag': '🥂 Happy New Year',
        'icons': {'main': '🎆', 'sub': '🥂', 'bot': '🍾', 'clock': '⏰', 'float': '✨'},
        'banner': {
            'title': 'CHÀO ĐÓN NĂM MỚI RỰC RỠ • VẠN SỰ NHƯ Ý',
            'sub': 'Trần Bình Auto chúc toàn thể anh em một năm mới tràn đầy sức khỏe, hạnh phúc và bứt phá thành công! 🥂🎉',
            'badge': '🎉 New Year Edition'
        },
        'colors': {
            'bg': '#070a14',
            'card_bg': '#0f172a',
            'border': '#1e293b',
            'border_focus': '#fbbf24',
            'primary': '#f59e0b',
            'primary_hover': '#d97706',
            'primary_gradient': 'linear-gradient(135deg, #d97706, #fbbf24)',
            'primary_glow': 'rgba(245, 158, 11, 0.4)',
            'accent': '#38bdf8',
            'text': '#f8fafc',
            'text_muted': '#94a3b8',
            'highlight': '#fef08a'
        },
        'bot_intro': 'Xin chào! 🎆 Tôi là Trợ Lý Trần Bình Auto (Phiên bản Chào Năm Mới). Chúc bạn một năm mới an khang thịnh vượng!'
    },

    # 2. TẾT NGUYÊN ĐÁN (11/01 - 05/02)
    'tet': {
        'key': 'tet',
        'name': 'Tết Nguyên Đán Cổ Truyền',
        'tag': '🧧 Chúc Mừng Năm Mới',
        'icons': {'main': '🌸', 'sub': '🌼', 'bot': '🧧', 'clock': '🏮', 'float': '🧧'},
        'banner': {
            'title': 'MỪNG XUÂN MỚI • VẠN SỰ NHƯ Ý',
            'sub': 'Kính chúc anh em Trần Bình Auto và gia đình năm mới Bình An - Thịnh Vượng - Tài Lộc Đầy Nhà! 🧧✨',
            'badge': '🌸 Happy Lunar New Year'
        },
        'colors': {
            'bg': '#130404',
            'card_bg': '#220808',
            'border': '#4c1212',
            'border_focus': '#ef4444',
            'primary': '#ef4444',
            'primary_hover': '#dc2626',
            'primary_gradient': 'linear-gradient(135deg, #dc2626, #f59e0b)',
            'primary_glow': 'rgba(239, 68, 68, 0.45)',
            'accent': '#fbbf24',
            'text': '#fff1f2',
            'text_muted': '#fca5a5',
            'highlight': '#fde047'
        },
        'bot_intro': 'Dạ xin chào! 🧧 Em là Trợ Lý Trần Bình Auto (Mừng Xuân Mới). Bạn cần tra cứu ca trực hay báo xin nghỉ Tết?'
    },

    # 3. LỄ TÌNH NHÂN VALENTINE (06/02 - 18/02)
    'valentine': {
        'key': 'valentine',
        'name': 'Lễ Tình Nhân Valentine',
        'tag': '💖 Happy Valentine',
        'icons': {'main': '🍫', 'sub': '🌹', 'bot': '💖', 'clock': '💝', 'float': '💌'},
        'banner': {
            'title': 'MÙA YÊU THƯƠNG • HAPPY VALENTINE',
            'sub': 'Chúc toàn thể anh em Trần Bình Auto luôn ngập tràn tình yêu thương, hạnh phúc bên một nửa của mình! 💖🍫',
            'badge': '🌹 Sweet Valentine'
        },
        'colors': {
            'bg': '#14060c',
            'card_bg': '#240c17',
            'border': '#4c182e',
            'border_focus': '#f43f5e',
            'primary': '#f43f5e',
            'primary_hover': '#e11d48',
            'primary_gradient': 'linear-gradient(135deg, #e11d48, #fb7185)',
            'primary_glow': 'rgba(244, 63, 94, 0.4)',
            'accent': '#fda4af',
            'text': '#fff1f2',
            'text_muted': '#fecdd3',
            'highlight': '#ffe4e6'
        },
        'bot_intro': 'Xin chào! 💖 Tôi là Trợ Lý Trần Bình Auto (Mùa Yêu Thương Valentine). Tôi có thể giúp gì cho bạn hôm nay?'
    },

    # 4. MÙA XUÂN TƯƠI MỚI (19/02 - 28/02)
    'spring': {
        'key': 'spring',
        'name': 'Mùa Xuân Tươi Mới',
        'tag': '🌱 Khởi Sắc Mùa Xuân',
        'icons': {'main': '🌿', 'sub': '🌱', 'bot': '🍀', 'clock': '🍃', 'float': '✨'},
        'banner': {
            'title': 'MÙA XUÂN KHỞI SẮC • NĂNG LƯỢNG TRÀN ĐẦY',
            'sub': 'Đầu năm phấn khởi, làm việc hăng say cùng anh em Trần Bình Auto phát triển vững mạnh! 🌿✨',
            'badge': '🍀 Fresh Spring'
        },
        'colors': {
            'bg': '#04130c',
            'card_bg': '#0a2318',
            'border': '#154530',
            'border_focus': '#10b981',
            'primary': '#10b981',
            'primary_hover': '#059669',
            'primary_gradient': 'linear-gradient(135deg, #059669, #34d399)',
            'primary_glow': 'rgba(16, 185, 129, 0.4)',
            'accent': '#6ee7b7',
            'text': '#ecfdf5',
            'text_muted': '#a7f3d0',
            'highlight': '#6ee7b7'
        },
        'bot_intro': 'Xin chào! 🍀 Tôi là Trợ Lý Mùa Xuân. Chúc bạn một ngày làm việc nhiều năng lượng và may mắn!'
    },

    # 5. QUỐC TẾ PHỤ NỮ 8/3 (01/03 - 15/03)
    'womens_day_mar': {
        'key': 'womens_day_mar',
        'name': 'Quốc Tế Phụ Nữ 8/3',
        'tag': '🌷 Happy Women\'s Day 8/3',
        'icons': {'main': '🌷', 'sub': '💐', 'bot': '🌸', 'clock': '🌺', 'float': '🎀'},
        'banner': {
            'title': 'CHÀO MỪNG NGÀY QUỐC TẾ PHỤ NỮ 8/3',
            'sub': 'Toàn thể anh em Trần Bình Auto xin gửi lời chúc yêu thương nhất đến các mẹ, người thương và toàn thể phái đẹp! 🌷💖',
            'badge': '💐 Mừng 8/3 Rạng Rỡ'
        },
        'colors': {
            'bg': '#12071a',
            'card_bg': '#200c30',
            'border': '#461b68',
            'border_focus': '#c084fc',
            'primary': '#a855f7',
            'primary_hover': '#9333ea',
            'primary_gradient': 'linear-gradient(135deg, #9333ea, #c084fc)',
            'primary_glow': 'rgba(168, 85, 247, 0.4)',
            'accent': '#e879f9',
            'text': '#faf5ff',
            'text_muted': '#e9d5ff',
            'highlight': '#f5d0fe'
        },
        'bot_intro': 'Xin chào! 🌷 Tôi là Trợ Lý Trần Bình Auto (Mừng Quốc Tế Phụ Nữ 8/3). Chúc các chị em luôn xinh đẹp và rạng ngời!'
    },

    # 6. THÁNG 3 BỨT PHÁ (16/03 - 05/04)
    'march_pro': {
        'key': 'march_pro',
        'name': 'Bứt Phá Mục Tiêu',
        'tag': '🚀 Chinh Phục Mục Tiêu',
        'icons': {'main': '🚀', 'sub': '⭐', 'bot': '💼', 'clock': '⏱️', 'float': '✨'},
        'banner': {
            'title': 'BỨT PHÁ MỤC TIÊU • ĐOÀN KẾT VỮNG TIẾN',
            'sub': 'Cùng anh em Trần Bình Auto nỗ lực làm việc hăng say, phục vụ khách hàng tận tâm và chu đáo! ⭐💪',
            'badge': '⭐ Tinh Thần Chuyên Nghiệp'
        },
        'colors': {
            'bg': '#060d1a',
            'card_bg': '#0d1b33',
            'border': '#1b325c',
            'border_focus': '#3b82f6',
            'primary': '#2563eb',
            'primary_hover': '#1d4ed8',
            'primary_gradient': 'linear-gradient(135deg, #1d4ed8, #60a5fa)',
            'primary_glow': 'rgba(37, 99, 235, 0.4)',
            'accent': '#38bdf8',
            'text': '#f0f9ff',
            'text_muted': '#bae6fd',
            'highlight': '#7dd3fc'
        },
        'bot_intro': 'Xin chào! 🚀 Tôi là Trợ Lý Trần Bình Auto. Hãy cùng nhau hoàn thành xuất sắc công việc hôm nay nhé!'
    },

    # 7. ĐẠI LỄ 30/4 & 1/5 & GIỖ TỔ (06/04 - 05/05)
    'liberation_day': {
        'key': 'liberation_day',
        'name': 'Đại Lễ 30/4 & 1/5 Hào Hùng',
        'tag': '🇻🇳 Non Sông Thống Nhất',
        'icons': {'main': '🇻🇳', 'sub': '⭐', 'bot': '🕊️', 'clock': '🎖️', 'float': '⭐'},
        'banner': {
            'title': 'CHÀO MỪNG ĐẠI LỄ 30/4 & QUỐC TẾ LAO ĐỘNG 1/5',
            'sub': 'Tự hào non sông Việt Nam gấm vóc! Chúc toàn thể anh em có kỳ nghỉ lễ vui vẻ, an toàn và tràn ngập niềm tự hào! 🇻🇳🎉',
            'badge': '⭐ Non Sông Thống Nhất'
        },
        'colors': {
            'bg': '#140404',
            'card_bg': '#240808',
            'border': '#501414',
            'border_focus': '#dc2626',
            'primary': '#dc2626',
            'primary_hover': '#b91c1c',
            'primary_gradient': 'linear-gradient(135deg, #b91c1c, #f59e0b)',
            'primary_glow': 'rgba(220, 38, 38, 0.45)',
            'accent': '#facc15',
            'text': '#fff1f2',
            'text_muted': '#fecdd3',
            'highlight': '#fef08a'
        },
        'bot_intro': 'Xin chào! 🇻🇳 Tôi là Trợ Lý Trần Bình Auto (Mừng Đại Lễ 30/4 - 1/5). Bạn muốn kiểm tra lịch trực hay ngày nghỉ lễ?'
    },

    # 8. MÙA HÈ RỰC RỠ (06/05 - 10/06)
    'summer': {
        'key': 'summer',
        'name': 'Mùa Hè Sôi Động',
        'tag': '🌊 Summer Vibes',
        'icons': {'main': '🌊', 'sub': '🌴', 'bot': '☀️', 'clock': '🍹', 'float': '🏄'},
        'banner': {
            'title': 'CHÀO HÈ RỰC RỠ • NĂNG ĐỘNG & SẢNG KHOÁI',
            'sub': 'Giải nhiệt mùa hè cùng anh em Trần Bình Auto, phục vụ khách hàng chu đáo và tràn đầy nhiệt huyết! 🌊🌴☀️',
            'badge': '🌴 Cool Summer'
        },
        'colors': {
            'bg': '#04121a',
            'card_bg': '#082333',
            'border': '#124564',
            'border_focus': '#06b6d4',
            'primary': '#0891b2',
            'primary_hover': '#0e7490',
            'primary_gradient': 'linear-gradient(135deg, #0e7490, #22d3ee)',
            'primary_glow': 'rgba(8, 145, 178, 0.4)',
            'accent': '#38bdf8',
            'text': '#ecfeff',
            'text_muted': '#a5f3fc',
            'highlight': '#67e8f9'
        },
        'bot_intro': 'Chào bạn! 🌊 Tôi là Trợ Lý Mùa Hè. Cùng giữ tinh thần sảng khoái và làm việc thật tốt hôm nay nhé!'
    },

    # 9. NGÀY GIA ĐÌNH VIỆT NAM (11/06 - 05/07)
    'family_day': {
        'key': 'family_day',
        'name': 'Ngày Gia Đình Việt Nam',
        'tag': '🏡 Mái Ấm Gia Đình',
        'icons': {'main': '🏡', 'sub': '👨‍👩‍👧', 'bot': '☕', 'clock': '🧡', 'float': '💖'},
        'banner': {
            'title': 'MỪNG NGÀY GIA ĐÌNH VIỆT NAM 28/6',
            'sub': 'Gia đình là điểm tựa vững chắc nhất. Chúc tổ ấm của toàn thể anh em Trần Bình Auto luôn bình an và ngập tràn tiếng cười! 🏡💖',
            'badge': '👨‍👩‍👧 Tình Thân Gắn Kết'
        },
        'colors': {
            'bg': '#0d0d12',
            'card_bg': '#191822',
            'border': '#343248',
            'border_focus': '#6366f1',
            'primary': '#4f46e5',
            'primary_hover': '#4338ca',
            'primary_gradient': 'linear-gradient(135deg, #4338ca, #818cf8)',
            'primary_glow': 'rgba(79, 70, 229, 0.4)',
            'accent': '#a5b4fc',
            'text': '#eef2ff',
            'text_muted': '#c7d2fe',
            'highlight': '#c7d2fe'
        },
        'bot_intro': 'Xin chào! 🏡 Tôi là Trợ Lý Trần Bình Auto (Mừng Ngày Gia Đình Việt Nam). Chúc bạn và gia đình luôn hạnh phúc!'
    },

    # 10. MÙA MƯA NHIỆT ĐỚI & CHILL (06/07 - 10/08)
    'rainy_chill': {
        'key': 'rainy_chill',
        'name': 'Mưa Rào Mát Mẻ',
        'tag': '🌦️ Mưa Rào Hạ Nhiệt',
        'icons': {'main': '🌦️', 'sub': '💧', 'bot': '🍃', 'clock': '☕', 'float': '🌧️'},
        'banner': {
            'title': 'GIỌT MƯA MÙA HẠ • THƯ GIÃN & MÁT LÀNH',
            'sub': 'Những cơn mưa xua tan cái nóng oi bức. Anh em đi làm chú ý an toàn và giữ gìn sức khỏe nhé! 🌦️☕',
            'badge': '💧 Chill & Relax'
        },
        'colors': {
            'bg': '#0a1012',
            'card_bg': '#132024',
            'border': '#223c44',
            'border_focus': '#14b8a6',
            'primary': '#0d9488',
            'primary_hover': '#0f766e',
            'primary_gradient': 'linear-gradient(135deg, #0f766e, #2dd4bf)',
            'primary_glow': 'rgba(13, 148, 136, 0.4)',
            'accent': '#5eead4',
            'text': '#f0fdfa',
            'text_muted': '#99f6e4',
            'highlight': '#5eead4'
        },
        'bot_intro': 'Chào bạn! 🌦️ Tôi là Trợ Lý Trần Bình Auto. Hôm nay trời mát mẻ, chúc bạn một ngày làm việc hiệu quả!'
    },

    # 11. MÙA THU LÃNG MẠN (11/08 - 25/08)
    'autumn': {
        'key': 'autumn',
        'name': 'Mùa Thu Lãng Mạn',
        'tag': '🍁 Autumn Breeze',
        'icons': {'main': '🍁', 'sub': '🍂', 'bot': '🍵', 'clock': '🌾', 'float': '🍂'},
        'banner': {
            'title': 'GẮN KẾT MÙA THU • HƯƠNG SẮC DỊU DÀNG',
            'sub': 'Gió thu se lạnh mang theo sự bình yên. Chúc anh em Trần Bình Auto một mùa thu tràn ngập niềm vui và ấm áp! 🍁🍵',
            'badge': '🍂 Mùa Thu Dịu Êm'
        },
        'colors': {
            'bg': '#120b06',
            'card_bg': '#22150d',
            'border': '#442b1a',
            'border_focus': '#d97706',
            'primary': '#b45309',
            'primary_hover': '#92400e',
            'primary_gradient': 'linear-gradient(135deg, #92400e, #f59e0b)',
            'primary_glow': 'rgba(180, 83, 9, 0.4)',
            'accent': '#fbbf24',
            'text': '#fffbeb',
            'text_muted': '#fde68a',
            'highlight': '#fef08a'
        },
        'bot_intro': 'Xin chào! 🍁 Tôi là Trợ Lý Mùa Thu. Chúc bạn có một ngày làm việc ấm áp và dễ chịu!'
    },

    # 12. QUỐC KHÁNH 2/9 (26/08 - 07/09)
    'national_day': {
        'key': 'national_day',
        'name': 'Quốc Khánh 2/9 Hào Hùng',
        'tag': '🇻🇳 Tết Độc Lập 2/9',
        'icons': {'main': '🇻🇳', 'sub': '⭐', 'bot': '🎆', 'clock': '🎖️', 'float': '⭐'},
        'banner': {
            'title': 'CHÀO MỪNG QUỐC KHÁNH NƯỚC CHXHCN VIỆT NAM 2/9',
            'sub': 'Mừng Tết Độc Lập! Tự hào lá cờ đỏ sao vàng tung bay khắp mọi nẻo đường đất nước! 🇻🇳🎆✨',
            'badge': '⭐ Tết Độc Lập 2/9'
        },
        'colors': {
            'bg': '#140404',
            'card_bg': '#240808',
            'border': '#501414',
            'border_focus': '#dc2626',
            'primary': '#dc2626',
            'primary_hover': '#b91c1c',
            'primary_gradient': 'linear-gradient(135deg, #b91c1c, #f59e0b)',
            'primary_glow': 'rgba(220, 38, 38, 0.45)',
            'accent': '#facc15',
            'text': '#fff1f2',
            'text_muted': '#fecdd3',
            'highlight': '#fef08a'
        },
        'bot_intro': 'Xin chào! 🇻🇳 Tôi là Trợ Lý Trần Bình Auto (Mừng Quốc Khánh 2/9). Chúc bạn kỳ nghỉ lễ tràn ngập niềm vui!'
    },

    # 13. TẾT TRUNG THU (08/09 - 30/09)
    'mid_autumn': {
        'key': 'mid_autumn',
        'name': 'Tết Trung Thu Đêm Rằm',
        'tag': '🌕 Vui Hội Trăng Rằm',
        'icons': {'main': '🌕', 'sub': '🥮', 'bot': '⭐', 'clock': '🏮', 'float': '🐇'},
        'banner': {
            'title': 'VUI HỘI TRĂNG RẰM • TẾT TRUNG THU SUM VẦY',
            'sub': 'Ánh trăng vàng soi sáng sự đoàn viên. Chúc anh em và gia đình một mùa Trung Thu ấm áp, ngọt ngào! 🥮🌕⭐',
            'badge': '🥮 Đêm Hội Trăng Rằm'
        },
        'colors': {
            'bg': '#070914',
            'card_bg': '#10152b',
            'border': '#1e2b52',
            'border_focus': '#fbbf24',
            'primary': '#f59e0b',
            'primary_hover': '#d97706',
            'primary_gradient': 'linear-gradient(135deg, #d97706, #fbbf24)',
            'primary_glow': 'rgba(245, 158, 11, 0.4)',
            'accent': '#fde047',
            'text': '#fefce8',
            'text_muted': '#fef08a',
            'highlight': '#fef08a'
        },
        'bot_intro': 'Xin chào! 🌕 Tôi là Trợ Lý Trung Thu. Chúc bạn và người thân một mùa trăng rằm ấm áp và hạnh phúc!'
    },

    # 14. NGÀY PHỤ NỮ VIỆT NAM 20/10 (01/10 - 25/10)
    'women_day': {
        'key': 'women_day',
        'name': 'Ngày Phụ Nữ Việt Nam 20/10',
        'tag': '💐 Mừng Ngày Phụ Nữ VN 20/10',
        'icons': {'main': '🌸', 'sub': '💐', 'bot': '🌸', 'clock': '🌷', 'float': '💐'},
        'banner': {
            'title': 'CHÀO MỪNG NGÀY PHỤ NỮ VIỆT NAM 20/10',
            'sub': 'Toàn thể anh em Trần Bình Auto xin gửi lời chúc yêu thương đến các bà, các mẹ, người thương và toàn thể phái đẹp nhân ngày 20/10 luôn ngập tràn niềm vui, xinh đẹp và rạng rỡ! 💖',
            'badge': '💝 Happy Women\'s Day'
        },
        'colors': {
            'bg': '#0d0614',
            'card_bg': '#190c24',
            'border': '#3b1740',
            'border_focus': '#f43f5e',
            'primary': '#f43f5e',
            'primary_hover': '#e11d48',
            'primary_gradient': 'linear-gradient(135deg, #e11d48, #db2777)',
            'primary_glow': 'rgba(244, 63, 94, 0.4)',
            'accent': '#fb7185',
            'text': '#f8fafc',
            'text_muted': '#fbcfe8',
            'highlight': '#fda4af'
        },
        'bot_intro': 'Xin chào! 🌸 Tôi là Trợ Lý Trần Bình Auto AI (Mừng Ngày Phụ Nữ VN 20/10 💐). Tôi có thể tra cứu lịch trực, kiểm tra ai nghỉ hoặc tạo đơn xin nghỉ bằng tin nhắn.'
    },

    # 15. LỄ HỘI HALLOWEEN (26/10 - 03/11)
    'halloween': {
        'key': 'halloween',
        'name': 'Lễ Hội Halloween',
        'tag': '🎃 Halloween Edition',
        'icons': {'main': '🎃', 'sub': '👻', 'bot': '🎃', 'clock': '🕯️', 'float': '🦇'},
        'banner': {
            'title': 'ĐÊM HỘI HALLOWEEN • RỰC RỠ & HUYỀN BÍ',
            'sub': 'Chúc toàn thể anh em Trần Bình Auto mùa Halloween vui vẻ, rộn ràng và tràn đầy năng lượng làm việc! 🎃✨🦇',
            'badge': '🎃 Happy Halloween'
        },
        'colors': {
            'bg': '#0b0914',
            'card_bg': '#151128',
            'border': '#2d2448',
            'border_focus': '#ea580c',
            'primary': '#ea580c',
            'primary_hover': '#c2410c',
            'primary_gradient': 'linear-gradient(135deg, #c2410c, #ea580c)',
            'primary_glow': 'rgba(234, 88, 12, 0.45)',
            'accent': '#fb923c',
            'text': '#f8fafc',
            'text_muted': '#fed7aa',
            'highlight': '#fb923c'
        },
        'bot_intro': 'Xin chào! 🎃 Tôi là Trợ Lý Trần Bình Auto AI (Phiên bản Halloween). Tôi có thể tra cứu lịch trực, kiểm tra ai nghỉ hoặc tạo đơn xin nghỉ bằng tin nhắn.'
    },

    # 16. NGÀY NHÀ GIÁO VIỆT NAM 20/11 (04/11 - 20/11)
    'teachers_day': {
        'key': 'teachers_day',
        'name': 'Tri Ân Thầy Cô 20/11',
        'tag': '📖 Tri Ân Thầy Cô 20/11',
        'icons': {'main': '📖', 'sub': '✒️', 'bot': '🎓', 'clock': '📝', 'float': '🌸'},
        'banner': {
            'title': 'KÍNH DÂNG TRI ÂN THẦY CÔ • NGÀY NHÀ GIÁO VN 20/11',
            'sub': 'Tôn sư trọng đạo! Nhớ ơn người đã dạy dỗ, chỉ bảo từng nét chữ và bài học đường đời cho chúng ta! 📖💐🎓',
            'badge': '🎓 Tri Ân Thầy Cô'
        },
        'colors': {
            'bg': '#070f1a',
            'card_bg': '#0d1e33',
            'border': '#18385e',
            'border_focus': '#0284c7',
            'primary': '#0284c7',
            'primary_hover': '#0369a1',
            'primary_gradient': 'linear-gradient(135deg, #0369a1, #38bdf8)',
            'primary_glow': 'rgba(2, 132, 199, 0.4)',
            'accent': '#38bdf8',
            'text': '#f0f9ff',
            'text_muted': '#bae6fd',
            'highlight': '#7dd3fc'
        },
        'bot_intro': 'Xin chào! 📖 Tôi là Trợ Lý Trần Bình Auto (Mừng Ngày Nhà Giáo VN 20/11). Chúc bạn một ngày làm việc ý nghĩa!'
    },

    # 17. BLACK FRIDAY & SIÊU SALE (21/11 - 30/11)
    'black_friday': {
        'key': 'black_friday',
        'name': 'Black Friday Cyberpunk',
        'tag': '⚡ Black Friday Super Sale',
        'icons': {'main': '⚡', 'sub': '🔥', 'bot': '🏷️', 'clock': '⚡', 'float': '🔥'},
        'banner': {
            'title': 'SIÊU SALE BLACK FRIDAY • BỨT PHÁ DOANH SỐ',
            'sub': 'Mùa mua sắm lớn nhất năm! Chúc anh em Trần Bình Auto bão đơn, năng lượng bốc lửa và phục vụ hết mình! ⚡🔥🏷️',
            'badge': '⚡ Cyber Super Sale'
        },
        'colors': {
            'bg': '#08080a',
            'card_bg': '#121217',
            'border': '#2a2a34',
            'border_focus': '#e11d48',
            'primary': '#e11d48',
            'primary_hover': '#be123c',
            'primary_gradient': 'linear-gradient(135deg, #e11d48, #f43f5e)',
            'primary_glow': 'rgba(225, 29, 72, 0.5)',
            'accent': '#fb7185',
            'text': '#fafafa',
            'text_muted': '#a1a1aa',
            'highlight': '#f43f5e'
        },
        'bot_intro': 'Xin chào! ⚡ Tôi là Trợ Lý Trần Bình Auto (Black Friday Edition). Sẵn sàng đồng hành cùng anh em chiến hết mình!'
    },

    # 18. GIÁNG SINH NOEL (01/12 - 25/12)
    'christmas': {
        'key': 'christmas',
        'name': 'Giáng Sinh Ấm Áp Noel',
        'tag': '🎄 Merry Christmas',
        'icons': {'main': '🎄', 'sub': '❄️', 'bot': '🎅', 'clock': '🔔', 'float': '❄️'},
        'banner': {
            'title': 'GIÁNG SINH AN LÀNH • MERRY CHRISTMAS',
            'sub': 'Chúc toàn thể anh em Trần Bình Auto và gia đình một mùa Giáng Sinh an lành, ấm áp và tràn ngập niềm vui! 🎄🎅❄️',
            'badge': '🎅 Merry Christmas'
        },
        'colors': {
            'bg': '#07140e',
            'card_bg': '#0f261c',
            'border': '#1e4836',
            'border_focus': '#16a34a',
            'primary': '#dc2626',
            'primary_hover': '#b91c1c',
            'primary_gradient': 'linear-gradient(135deg, #dc2626, #16a34a)',
            'primary_glow': 'rgba(220, 38, 38, 0.4)',
            'accent': '#4ade80',
            'text': '#f0fdf4',
            'text_muted': '#bbf7d0',
            'highlight': '#86efac'
        },
        'bot_intro': 'Ho ho ho! 🎅 Tôi là Trợ Lý Giáng Sinh. Chúc bạn và anh em một mùa Noel an lành, ấm áp!'
    }
}

# LỊCH TRÌNH TỰ ĐỘNG ĐỔI GIAO DIỆN TRONG NĂM (Tháng, Ngày) -> (Tháng, Ngày)
# Đổi trước ngày lễ từ 5 đến 15 ngày để Trần Bình Auto luôn rộn ràng không khí!
THEMES_TIMELINE = [
    # Tháng 1
    {'theme': 'new_year',         'start': (12, 26), 'end': (1, 10)},
    {'theme': 'tet',              'start': (1, 11),  'end': (2, 5)},
    # Tháng 2
    {'theme': 'valentine',        'start': (2, 6),   'end': (2, 18)},
    {'theme': 'spring',           'start': (2, 19),  'end': (2, 29)},
    # Tháng 3
    {'theme': 'womens_day_mar',   'start': (3, 1),   'end': (3, 15)},
    {'theme': 'march_pro',        'start': (3, 16),  'end': (4, 5)},
    # Tháng 4
    {'theme': 'liberation_day',   'start': (4, 6),   'end': (5, 5)},
    # Tháng 5
    {'theme': 'summer',           'start': (5, 6),   'end': (6, 10)},
    # Tháng 6
    {'theme': 'family_day',       'start': (6, 11),  'end': (7, 5)},
    # Tháng 7
    {'theme': 'rainy_chill',      'start': (7, 6),   'end': (8, 10)},
    # Tháng 8
    {'theme': 'autumn',           'start': (8, 11),  'end': (8, 25)},
    {'theme': 'national_day',     'start': (8, 26),  'end': (9, 7)},
    # Tháng 9
    {'theme': 'mid_autumn',       'start': (9, 8),   'end': (9, 30)},
    # Tháng 10
    {'theme': 'women_day',        'start': (10, 1),  'end': (10, 25)},
    {'theme': 'halloween',        'start': (10, 26), 'end': (11, 3)},
    # Tháng 11
    {'theme': 'teachers_day',     'start': (11, 4),  'end': (11, 20)},
    {'theme': 'black_friday',     'start': (11, 21), 'end': (11, 30)},
    # Tháng 12
    {'theme': 'christmas',        'start': (12, 1),  'end': (12, 25)},
]

def get_theme_for_date(check_date):
    """
    Xác định theme theo ngày tháng năm thực tế (so khớp Month, Day).
    Tự động áp dụng cho mọi năm mà không cần cập nhật lại năm.
    """
    m = check_date.month
    d = check_date.day

    for slot in THEMES_TIMELINE:
        s_m, s_d = slot['start']
        e_m, e_d = slot['end']

        # Cùng một năm dương lịch
        if s_m <= e_m:
            if (m > s_m or (m == s_m and d >= s_d)) and (m < e_m or (m == e_m and d <= e_d)):
                return THEMES_CATALOG.get(slot['theme'], THEMES_CATALOG['women_day'])
        else:
            # Giao thừa vắt qua năm mới (VD: 26/12 đến 10/01)
            if (m > s_m or (m == s_m and d >= s_d)) or (m < e_m or (m == e_m and d <= e_d)):
                return THEMES_CATALOG.get(slot['theme'], THEMES_CATALOG['women_day'])

    return THEMES_CATALOG['women_day']

def get_theme_by_key(key):
    """Lấy theme theo key cụ thể"""
    return THEMES_CATALOG.get(key, THEMES_CATALOG['women_day'])

