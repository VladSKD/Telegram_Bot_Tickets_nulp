import { useState, useEffect, useRef } from 'react';
import './App.css';

const tg = window.Telegram.WebApp;

function App() {
  const [selectedSeats, setSelectedSeats] = useState([]);
  const [occupiedSeats, setOccupiedSeats] = useState([]);
  
  // Додаємо стани для адмін-режиму
  const [isAdmin, setIsAdmin] = useState(false);
  const [eventId, setEventId] = useState(null);

  const selectedSeatsRef = useRef(selectedSeats);

  useEffect(() => {
    selectedSeatsRef.current = selectedSeats;
    
    if (selectedSeats.length > 0) {
      // Кнопка змінює текст залежно від режиму
      tg.MainButton.text = isAdmin 
        ? `ДІЗНАТИСЯ ІНФО (Ряд ${selectedSeats[0].row}, Місце ${selectedSeats[0].seat})` 
        : `🎟 КУПИТИ (${selectedSeats.length} шт.)`;
      tg.MainButton.show();
    } else {
      tg.MainButton.hide();
    }
  }, [selectedSeats, isAdmin]);

  useEffect(() => {
    tg.expand();
    tg.ready();
    
    const queryParams = new URLSearchParams(window.location.search);
    const occParam = queryParams.get('occ');
    if (occParam) setOccupiedSeats(occParam.split(','));
    
    // Перевіряємо, чи це зайшов адмін
    if (queryParams.get('admin') === 'true') setIsAdmin(true);
    if (queryParams.get('ev_id')) setEventId(queryParams.get('ev_id'));

    const handleMainButtonClick = () => {
      const dataToSend = selectedSeatsRef.current;
      if (dataToSend.length > 0) {
        if (isAdmin) {
          // Відправляємо спеціальний код для адміна: admin_seat|ev_id|row-seat
          tg.sendData(`admin_seat|${eventId}|${dataToSend[0].row}-${dataToSend[0].seat}`);
        } else {
          // Звичайний формат для покупця
          const dataString = dataToSend.map(s => `${s.row}-${s.seat}`).join('|');
          tg.sendData(dataString);
        }
      } else {
        tg.showAlert("Будь ласка, оберіть місця!");
      }
    };

    tg.MainButton.onClick(handleMainButtonClick);
    return () => tg.MainButton.offClick(handleMainButtonClick);
  }, [isAdmin, eventId]);

  const toggleSeat = (row, seatNum) => {
    const seatId = `${row}-${seatNum}`;
    const isOccupied = occupiedSeats.includes(seatId);

    if (isAdmin) {
      // АДМІН: Може виділяти ТІЛЬКИ зайняті (червоні) місця і тільки по 1 штуці
      if (!isOccupied) return;
      
      setSelectedSeats(prev => {
        // Якщо клікнули по вже виділеному — знімаємо виділення, інакше виділяємо нове
        return prev.some(s => s.id === seatId) ? [] : [{ id: seatId, row, seat: seatNum }];
      });
    } else {
      // ПОКУПЕЦЬ: Блокуємо клік, якщо місце зайняте
      if (isOccupied) return;
      
      setSelectedSeats(prev => {
        if (prev.some(s => s.id === seatId)) {
          return prev.filter(s => s.id !== seatId);
        }
        return [...prev, { id: seatId, row, seat: seatNum }];
      });
    }
  };

  

  const hallConfig = [
    { row: '24', left: 3, right: 3 }, { row: '23', left: 3, right: 3 },
    { row: '22', left: 3, right: 3 }, { row: '21', left: 3, right: 3 },
    { row: '20', left: 3, right: 3 }, { row: '19', left: 3, right: 3 },
    { row: '18', left: 3, right: 3 }, { row: '17', left: 3, right: 3 },
    { row: '16', left: 3, right: 3 }, { row: '15', left: 3, right: 3 },
    { row: '14', left: 3, right: 3 },
    { isAisle: true, label: '' },
    { row: '13', left: 6, right: 6 },
    { isAisle: true, label: 'ПРОХІД' },
    { row: '12Б', left: 6, right: 6 }, { row: '12А', left: 6, right: 6 },
    { row: '12', left: 6, right: 6 }, { row: '11', left: 6, right: 6 },
    { row: '10', left: 6, right: 6 }, { row: '9', left: 6, right: 6 },
    { row: '8', left: 6, right: 6 }, { row: '7', left: 6, right: 6 },
    { row: '6', left: 6, right: 6 },
    { isAisle: true, label: 'ПРОХІД' },
    { row: '5Б', left: 6, right: 6 }, { row: '5А', left: 6, right: 6 },
    { row: '5', left: 6, right: 6 }, { row: '4', left: 6, right: 6 },
    { row: '3', left: 6, right: 6 }, { row: '2', left: 6, right: 6 },
    { row: '1', left: 6, right: 6 }
  ];

  const renderSeats = (rowCount, rowLabel, startSeatNum) => {
    return Array.from({ length: rowCount }).map((_, i) => {
      const seatNum = startSeatNum + i;
      const seatId = `${rowLabel}-${seatNum}`;
      const isOccupied = occupiedSeats.includes(seatId);
      const isSelected = selectedSeats.some(s => s.id === seatId);

      let className = 'seat available';
      if (isOccupied) className = 'seat occupied';
      
      // 👈 Важливо: додаємо клас selected, навіть якщо місце зайняте (для адміна)
      if (isSelected) className += ' selected';

      return (
        <button
          key={seatId}
          className={className}
          onClick={() => toggleSeat(rowLabel, seatNum)}
          // 👈 ОСЬ ТУТ БУВ БАГ: тепер кнопка активна для адміна, навіть якщо вона червона
          disabled={!isAdmin && isOccupied}
        >
          {seatNum}
        </button>
      );
    });
  };

  return (
    <div className={`hall-wrapper ${isAdmin ? 'admin-mode' : ''}`}>
      <h2>Органний зал {isAdmin ? '(АДМІН)' : ''}</h2>
      
      <div className="hall-container">
        {hallConfig.map((item, index) => {
          if (item.isAisle) {
            return <div key={`aisle-${index}`} className="aisle-marker">{item.label}</div>;
          }

          return (
            <div key={`row-${item.row}`} className="row-wrapper">
              <span className="row-label">{item.row}</span>
              
              <div className="seats-group">
                {renderSeats(item.left, item.row, 1)}
              </div>
              
              <div className="center-aisle"></div>
              
              <div className="seats-group">
                {renderSeats(item.right, item.row, item.left + 1)}
              </div>
              
              <span className="row-label">{item.row}</span>
            </div>
          );
        })}
      </div>

      <div className="stage-container">
        <div className="stage">СЦЕНА</div>
        <p className="stage-subtitle">Тут творять магію музики</p>
      </div>

      <div className="legend">
        <div className="legend-item"><span className="seat available legend-dot"></span> Вільне</div>
        <div className="legend-item"><span className="seat occupied legend-dot"></span> Зайняте</div>
        <div className="legend-item"><span className="seat selected legend-dot"></span> Обране</div>
      </div>
    </div>
  );
}

export default App;