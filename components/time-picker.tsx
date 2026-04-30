import React from 'react';
import {
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  FlatList,
} from 'react-native';
import Icon from 'react-native-vector-icons/Ionicons';

interface TimePickerProps {
  visible: boolean;
  selectedTime: string;
  onClose: () => void;
  onTimeSelect: (time: string) => void;
}

export default function TimePicker({ visible, selectedTime, onClose, onTimeSelect }: TimePickerProps) {
  const generateTimeSlots = () => {
    const times: string[] = [];
    for (let hour = 0; hour < 24; hour++) {
      for (let minute = 0; minute < 60; minute += 15) {
        const hourStr = String(hour).padStart(2, '0');
        const minuteStr = String(minute).padStart(2, '0');
        times.push(`${hourStr}:${minuteStr}`);
      }
    }
    return times;
  };

  const timeSlots = generateTimeSlots();

  const renderTimeSlot = ({ item }: { item: string }) => {
    const isSelected = item === selectedTime;
    
    return (
      <TouchableOpacity
        style={[styles.timeSlot, isSelected && styles.selectedTimeSlot]}
        onPress={() => {
          onTimeSelect(item);
          onClose();
        }}
      >
        <Text style={[styles.timeText, isSelected && styles.selectedTimeText]}>
          {item}
        </Text>
        {isSelected && (
          <Icon name="checkmark" size={20} color="#007AFF" />
        )}
      </TouchableOpacity>
    );
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <View style={styles.container}>
          <View style={styles.header}>
            <Text style={styles.title}>Выберите время</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeButton}>
              <Icon name="close" size={28} color="#666" />
            </TouchableOpacity>
          </View>

          <FlatList
            data={timeSlots}
            renderItem={renderTimeSlot}
            keyExtractor={(item) => item}
            showsVerticalScrollIndicator={true}
            contentContainerStyle={styles.listContent}
          />
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  container: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: '80%',
    paddingBottom: 30,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1a1a1a',
  },
  closeButton: {
    padding: 4,
  },
  listContent: {
    paddingHorizontal: 20,
    paddingVertical: 8,
  },
  timeSlot: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  selectedTimeSlot: {
    backgroundColor: '#E3F2FD',
    borderRadius: 12,
    paddingHorizontal: 20,
  },
  timeText: {
    fontSize: 18,
    color: '#1a1a1a',
  },
  selectedTimeText: {
    color: '#007AFF',
    fontWeight: '600',
  },
});
