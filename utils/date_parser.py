    import re
    import dateparser
    from dateparser.search import search_dates


    def parse_datetime_from_text(text):
        """Извлечь дату и время из текста"""
        result = {
            'date': '',
            'time': '',
            'has_date': False,
            'has_time': False,
        }

        if not text or not text.strip():
            return result

        # Сначала ищем время формата HH:MM через regex 
        time_match = re.search(r'\b(\d{1,2}):(\d{2})\b', text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                result['time'] = f'{hour:02d}:{minute:02d}'
                result['has_time'] = True

        # Ищем дату через dateparser
        try:
            settings = {
                'PREFER_DATES_FROM': 'future',
                'RETURN_AS_TIMEZONE_AWARE': False,
            }
            found = search_dates(text, languages=['ru', 'en'], settings=settings)
            if found:
                _, parsed = found[0]
                result['date'] = parsed.strftime('%Y-%m-%d')
                result['has_date'] = True
                # Если regex не нашёл время, берём из dateparser
                if not result['has_time'] and (parsed.hour or parsed.minute):
                    result['time'] = parsed.strftime('%H:%M')
                    result['has_time'] = True
        except Exception as e:
            print(f'Ошибка парсинга даты: {e}')

        return result
