import * as chrono from 'chrono-node';

export interface ParsedDateTime {
  date: string;
  time: string;
  hasDate: boolean;
  hasTime: boolean;
}

export function parseDateTimeFromText(text: string): ParsedDateTime {
  const result: ParsedDateTime = {
    date: '',
    time: '',
    hasDate: false,
    hasTime: false,
  };

  if (!text || text.trim().length === 0) {
    return result;
  }

  try {
    const parsedResults = chrono.ru.parse(text, new Date(), { forwardDate: true });
    
    if (parsedResults.length > 0) {
      const parsed = parsedResults[0];
      const parsedDate = parsed.start.date();

      // Форматируем дату в YYYY-MM-DD
      const year = parsedDate.getFullYear();
      const month = String(parsedDate.getMonth() + 1).padStart(2, '0');
      const day = String(parsedDate.getDate()).padStart(2, '0');
      result.date = `${year}-${month}-${day}`;
      result.hasDate = true;

      // Форматируем время в HH:MM
      const hours = String(parsedDate.getHours()).padStart(2, '0');
      const minutes = String(parsedDate.getMinutes()).padStart(2, '0');
      result.time = `${hours}:${minutes}`;
      result.hasTime = true;
    }
  } catch (error) {
    console.error('Ошибка парсинга даты:', error);
  }

  return result;
}
