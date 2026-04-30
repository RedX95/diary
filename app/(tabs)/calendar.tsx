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

export default function CalendarScreen() {
  const [task, setTask] = useState('');
  const [time, setTime] = useState('');
  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  });
  const [tasks, setTasks] = useState<Task[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showTimePicker, setShowTimePicker] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

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
    const finalDate = parsed.hasDate ? parsed.date : selectedDate;

    if (!finalTime.trim()) {
      Alert.alert('Ошибка', 'Укажите время в тексте или выберите вручную');
      return;
    }

    const timeRegex = /^([01]\d|2[0-3]):([0-5]\d)$/;
    if (!timeRegex.test(finalTime)) {
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

    const updatedTasks = [newTask, ...tasks];
    setTasks(updatedTasks);
    saveTasks(updatedTasks);

    setTask('');
    setTime('');
    setShowAddModal(false);
    Keyboard.dismiss();
  }, [task, time, selectedDate, tasks]);

  // Авто-заполнение времени при изменении текста
  const handleTaskChange = (newText: string) => {
    setTask(newText);
    if (!time) {
      const parsed = parseDateTimeFromText(newText);
      if (parsed.hasTime) {
        setTime(parsed.time);
      }
      if (parsed.hasDate) {
        setSelectedDate(parsed.date);
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

  const formatDateFull = (dateStr: string) => {
    const date = new Date(dateStr);
    const options: Intl.DateTimeFormatOptions = { 
      weekday: 'long', 
      day: 'numeric', 
      month: 'long',
      year: 'numeric'
    };
    return date.toLocaleDateString('ru-RU', options);
  };

  const filteredTasks = tasks.filter(item => item.date === selectedDate);

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
      <Text style={styles.title}>Календарь задач</Text>

      <Calendar
        selectedDate={selectedDate}
        onDateSelect={setSelectedDate}
      />

      <View style={styles.dateHeader}>
        <Text style={styles.dateHeaderText}>{formatDateFull(selectedDate)}</Text>
        <TouchableOpacity 
          style={styles.addTaskButton}
          onPress={() => setShowAddModal(true)}
        >
          <Icon name="add" size={20} color="#fff" />
          <Text style={styles.addTaskButtonText}>Добавить</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={filteredTasks}
        renderItem={renderTask}
        keyExtractor={item => item.id}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.listContent}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Icon name="calendar-outline" size={60} color="#ddd" />
            <Text style={styles.emptyText}>Нет задач на этот день</Text>
          </View>
        }
      />

      <Modal
        visible={showAddModal}
        transparent
        animationType="slide"
        onRequestClose={() => setShowAddModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Новая задача</Text>
            
            <TextInput
              style={styles.modalInput}
              placeholder="Что нужно сделать?"
              value={task}
              onChangeText={handleTaskChange}
              placeholderTextColor="#999"
            />

            <TouchableOpacity
              style={styles.modalInput}
              onPress={() => setShowTimePicker(true)}
            >
              <Text style={time ? styles.timeValue : styles.timePlaceholder}>
                {time || 'Время (HH:MM)'}
              </Text>
            </TouchableOpacity>

            <Text style={styles.modalDateText}>
              Дата: {formatDateDisplay(selectedDate)}
            </Text>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, styles.cancelButton]}
                onPress={() => {
                  setShowAddModal(false);
                  setTask('');
                  setTime('');
                }}
              >
                <Text style={styles.cancelButtonText}>Отмена</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[styles.modalButton, styles.confirmButton]}
                onPress={addTask}
              >
                <Text style={styles.confirmButtonText}>Добавить</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

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
  dateHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginTop: 20,
    marginBottom: 10,
  },
  dateHeaderText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1a1a1a',
  },
  addTaskButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#007AFF',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    gap: 4,
  },
  addTaskButtonText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '600',
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
    marginRight: 12,
  },
  timeText: {
    fontSize: 15,
    fontWeight: '600',
    color: '#007AFF',
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
    marginTop: 60,
  },
  emptyText: {
    fontSize: 18,
    color: '#aaa',
    marginTop: 16,
    fontWeight: '600',
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
    padding: 24,
    width: '100%',
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#1a1a1a',
    marginBottom: 20,
    textAlign: 'center',
  },
  modalInput: {
    backgroundColor: '#f8f9fa',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 16,
    borderWidth: 1,
    borderColor: '#e0e0e0',
    marginBottom: 12,
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
  modalDateText: {
    fontSize: 16,
    color: '#666',
    marginBottom: 20,
    textAlign: 'center',
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
  },
  modalButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  cancelButton: {
    backgroundColor: '#f0f0f0',
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#666',
  },
  confirmButton: {
    backgroundColor: '#007AFF',
  },
  confirmButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
});
