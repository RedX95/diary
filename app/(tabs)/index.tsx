import Calendar from '@/components/calendar';
import TimePicker from '@/components/time-picker';
import { parseDateTimeFromText } from '@/utils/date-parser';
import { storage } from '@/utils/storage';
import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  FlatList,
  Keyboard,
  Modal,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { Swipeable } from 'react-native-gesture-handler';
import Icon from 'react-native-vector-icons/Ionicons';

type Task = {
  id: string;
  text: string;
  time: string;
  date: string;
  completed: boolean;
  createdAt: number;
};

const STORAGE_KEY = '@tasks';

export default function App() {
  const [task, setTask] = useState('');
  const [time, setTime] = useState('');
  const [date, setDate] = useState(() => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  });
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Загрузка задач из AsyncStorage
  useEffect(() => {
    const loadTasks = async () => {
      try {
        const savedTasks = await storage.getItem(STORAGE_KEY);
        if (savedTasks) {
          const parsedTasks = JSON.parse(savedTasks);
          // Миграция: добавляем поле date старым задачам
          const today = new Date();
          const year = today.getFullYear();
          const month = String(today.getMonth() + 1).padStart(2, '0');
          const day = String(today.getDate()).padStart(2, '0');
          const defaultDate = `${year}-${month}-${day}`;
          
          const migratedTasks = parsedTasks.map((task: any) => ({
            ...task,
            date: task.date || defaultDate,
          }));
          
          setTasks(migratedTasks);
          // Сохраняем мигрированные данные
          await storage.setItem(STORAGE_KEY, JSON.stringify(migratedTasks));
        }
      } catch (error) {
        console.error('Ошибка загрузки задач:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadTasks();
  }, []);

  // Сохранение задач
  const saveTasks = async (newTasks: Task[]) => {
    try {
      await storage.setItem(STORAGE_KEY, JSON.stringify(newTasks));
    } catch (error) {
      console.error('Ошибка сохранения задач:', error);
    }
  };

  const addTask = useCallback(() => {
    if (!task.trim()) {
      Alert.alert('Ошибка', 'Заполните задачу');
      return;
    }

    // Парсим дату и время из текста
    const parsed = parseDateTimeFromText(task);
    const finalTime = time || parsed.time;
    const finalDate = parsed.hasDate ? parsed.date : date;

    if (!finalTime.trim()) {
      Alert.alert('Ошибка', 'Укажите время в тексте или выберите вручную');
      return;
    }

    if (!date.trim()) {
      Alert.alert('Ошибка', 'Выберите дату');
      return;
    }

    // Простая валидация времени (формат HH:MM)
    const timeRegex = /^([01]\d|2[0-3]):([0-5]\d)$/;
    if (!timeRegex.test(time)) {
      Alert.alert('Ошибка', 'Введите время в формате HH:MM (например: 18:30)');
      return;
    }

    const newTask: Task = {
      id: Date.now().toString(),
      text: task.trim(),
      time: finalTime.trim(),
      date: finalDate,
      completed: false,
      createdAt: Date.now(),
    };

    const updatedTasks = [newTask, ...tasks]; // новые задачи сверху
    setTasks(updatedTasks);
    saveTasks(updatedTasks);

    setTask('');
    setTime('');
    Keyboard.dismiss();
  }, [task, time, date, tasks]);

  // Авто-заполнение времени при изменении текста
  const handleTaskChange = (newText: string) => {
    setTask(newText);
    if (!time) {
      const parsed = parseDateTimeFromText(newText);
      if (parsed.hasTime) {
        setTime(parsed.time);
      }
      if (parsed.hasDate) {
        setDate(parsed.date);
      }
    }
  };

  const toggleComplete = (id: string) => {
    const updatedTasks = tasks.map(item =>
      item.id === id ? { ...item, completed: !item.completed } : item
    );
    setTasks(updatedTasks);
    saveTasks(updatedTasks);
  };

  const deleteTask = (id: string) => {
    const updatedTasks = tasks.filter(item => item.id !== id);
    setTasks(updatedTasks);
    saveTasks(updatedTasks);
  };

  const formatDateDisplay = (dateStr: string) => {
    const date = new Date(dateStr);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${day}.${month}`;
  };

  const [showCalendar, setShowCalendar] = useState(false);
  const [showTimePicker, setShowTimePicker] = useState(false);

  const renderTask = ({ item }: { item: Task }) => {
    const renderRightActions = () => (
      <TouchableOpacity
        style={styles.deleteButton}
        onPress={() => deleteTask(item.id)}
      >
        <Icon name="trash-outline" size={24} color="#fff" />
      </TouchableOpacity>
    );

    return (
      <Swipeable renderRightActions={renderRightActions}>
        <TouchableOpacity
          style={[
            styles.taskContainer,
            item.completed && styles.taskCompleted,
          ]}
          onPress={() => toggleComplete(item.id)}
          activeOpacity={0.7}
        >
          <View style={styles.taskContent}>
            <View style={styles.timeContainer}>
              <Text style={styles.timeText}>{item.time}</Text>
            </View>

            <View style={styles.dateContainer}>
              <Text style={styles.dateText}>{formatDateDisplay(item.date)}</Text>
            </View>

            <View style={styles.taskTextContainer}>
              <Text
                style={[
                  styles.taskText,
                  item.completed && styles.taskTextCompleted,
                ]}
              >
                {item.text}
              </Text>
            </View>

            <View style={styles.checkbox}>
              {item.completed ? (
                <Icon name="checkmark-circle" size={24} color="#4CAF50" />
              ) : (
                <Icon name="ellipse-outline" size={24} color="#666" />
              )}
            </View>
          </View>
        </TouchableOpacity>
      </Swipeable>
    );
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Мои задачи</Text>

      {/* Форма добавления */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          placeholder="Что нужно сделать?"
          value={task}
          onChangeText={handleTaskChange}
          placeholderTextColor="#999"
          returnKeyType="next"
          onSubmitEditing={() => {
            // фокус на поле времени (можно улучшить через ref)
          }}
        />

        <TouchableOpacity
          style={[styles.input, styles.timeInput, styles.timeButton]}
          onPress={() => setShowTimePicker(true)}
        >
          <Text style={time ? styles.timeValue : styles.timePlaceholder}>
            {time || '18:30'}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.dateButton} onPress={() => setShowCalendar(true)}>
          <Text style={styles.dateButtonText}>{formatDateDisplay(date)}</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.addButton} onPress={addTask}>
          <Icon name="add" size={28} color="#fff" />
        </TouchableOpacity>
      </View>

      {/* Список задач */}
      <FlatList
        data={tasks}
        renderItem={renderTask}
        keyExtractor={item => item.id}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="list-outline" size={60} color="#ddd" />
            <Text style={styles.emptyText}>Пока нет задач</Text>
            <Text style={styles.emptySubtext}>Добавьте первую задачу выше</Text>
          </View>
        }
      />

      {/* Модальное окно календаря */}
      <Modal
        visible={showCalendar}
        transparent
        animationType="fade"
        onRequestClose={() => setShowCalendar(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Calendar
              selectedDate={date}
              onDateSelect={(selectedDate) => {
                setDate(selectedDate);
                setShowCalendar(false);
              }}
            />
            <TouchableOpacity
              style={styles.closeModalButton}
              onPress={() => setShowCalendar(false)}
            >
              <Text style={styles.closeModalText}>Отмена</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* TimePicker */}
      <TimePicker
        visible={showTimePicker}
        selectedTime={time}
        onClose={() => setShowTimePicker(false)}
        onTimeSelect={setTime}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
    paddingTop: Platform.OS === 'ios' ? 60 : 40,
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#1a1a1a',
    textAlign: 'center',
    marginBottom: 20,
  },
  inputContainer: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    gap: 10,
    marginBottom: 20,
  },
  input: {
    flex: 1,
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    borderWidth: 1,
    borderColor: '#e0e0e0',
  },
  timeInput: {
    width: 100,
  },
  timeButton: {
    justifyContent: 'center',
  },
  timeValue: {
    fontSize: 16,
    color: '#1a1a1a',
    fontWeight: '600',
  },
  timePlaceholder: {
    fontSize: 16,
    color: '#999',
  },
  addButton: {
    backgroundColor: '#007AFF',
    width: 56,
    height: 56,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#007AFF',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  listContent: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  taskContainer: {
    backgroundColor: '#fff',
    borderRadius: 16,
    marginBottom: 12,
    padding: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 3,
  },
  taskCompleted: {
    opacity: 0.85,
  },
  taskContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  timeContainer: {
    backgroundColor: '#f0f0f0',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginRight: 8,
  },
  timeText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#007AFF',
  },
  dateContainer: {
    backgroundColor: '#E8F5E9',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    marginRight: 12,
  },
  dateText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#4CAF50',
  },
  taskTextContainer: {
    flex: 1,
  },
  taskText: {
    fontSize: 17,
    color: '#1a1a1a',
    lineHeight: 24,
  },
  taskTextCompleted: {
    textDecorationLine: 'line-through',
    color: '#888',
  },
  checkbox: {
    marginLeft: 8,
  },
  deleteButton: {
    backgroundColor: '#FF3B30',
    justifyContent: 'center',
    alignItems: 'center',
    width: 80,
    borderTopRightRadius: 16,
    borderBottomRightRadius: 16,
  },
  emptyContainer: {
    alignItems: 'center',
    marginTop: 100,
  },
  emptyText: {
    fontSize: 20,
    color: '#aaa',
    marginTop: 16,
    fontWeight: '600',
  },
  emptySubtext: {
    fontSize: 15,
    color: '#ccc',
    marginTop: 8,
  },
  dateButton: {
    backgroundColor: '#fff',
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: '#007AFF',
    minWidth: 70,
    alignItems: 'center',
  },
  dateButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 20,
    width: '100%',
    maxWidth: 400,
  },
  closeModalButton: {
    marginTop: 16,
    padding: 12,
    borderRadius: 8,
    backgroundColor: '#f0f0f0',
    alignItems: 'center',
  },
  closeModalText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#666',
  },
});