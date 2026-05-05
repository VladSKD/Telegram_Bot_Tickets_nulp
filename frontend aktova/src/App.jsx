import { useState, useEffect, useRef } from 'react';
import './App.css';

const tg = window.Telegram.WebApp;

function App() {
  const [selectedSeats, setSelectedSeats] = useState([]);
  const [occupiedSeats, setOccupiedSeats] = useState([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [eventId, setEventId] = useState(null);

  const selectedSeatsRef = useRef(selectedSeats);

  useEffect(() => {
    selectedSeatsRef.current = selectedSeats;
    if (selectedSeats.length > 0) {
      tg.MainButton.text = isAdmin 
        ? `ДІЗНАТИСЯ ІНФО (Місце обрано)` 
        : `🎟 КУПИТИ (${selectedSeats.length} шт.)`;
      tg.MainButton.show();
    } else {
      tg.MainButton.hide();
    }
  }, [selectedSeats, isAdmin]);

  useEffect(() => {
    tg.expand();
    tg.ready();
    
    // Отримуємо зайняті місця. Через велику кількість, вони передаються через кому
    const queryParams = new URLSearchParams(window.location.search);
    const occParam = queryParams.get('occ');
    if (occParam) setOccupiedSeats(occParam.split(','));
    
    if (queryParams.get('admin') === 'true') setIsAdmin(true);
    if (queryParams.get('ev_id')) setEventId(queryParams.get('ev_id'));

    const handleMainButtonClick = () => {
      const dataToSend = selectedSeatsRef.current;
      if (dataToSend.length > 0) {
        if (isAdmin) {
          tg.sendData(`admin_seat|${eventId}|${dataToSend[0].id}`);
        } else {
          // Відправляємо у форматі: Зона-Ряд-Місце|Зона-Ряд-Місце
          const dataString = dataToSend.map(s => s.id).join('|');
          tg.sendData(dataString);
        }
      } else {
        tg.showAlert("Будь ласка, оберіть місця!");
      }
    };

    tg.MainButton.onClick(handleMainButtonClick);
    return () => tg.MainButton.offClick(handleMainButtonClick);
  }, [isAdmin, eventId]);

  const toggleSeat = (zone, row, seatNum) => {
    const seatId = `${zone}-${row}-${seatNum}`;
    const isOccupied = occupiedSeats.includes(seatId);

    if (isAdmin) {
      if (!isOccupied) return;
      setSelectedSeats(prev => prev.some(s => s.id === seatId) ? [] : [{ id: seatId, zone, row, seat: seatNum }]);
    } else {
      if (isOccupied) return;
      setSelectedSeats(prev => {
        if (prev.some(s => s.id === seatId)) return prev.filter(s => s.id !== seatId);
        return [...prev, { id: seatId, zone, row, seat: seatNum }];
      });
    }
  };

  // --- ГЕНЕРАТОРИ РЯДІВ ---
  const renderRow = (zone, rowNum, seatCount) => {
    return Array.from({ length: seatCount }).map((_, i) => {
      const seatNum = i + 1;
      const seatId = `${zone}-${rowNum}-${seatNum}`;
      const isOccupied = occupiedSeats.includes(seatId);
      const isSelected = selectedSeats.some(s => s.id === seatId);

      let className = `seat ${isOccupied ? 'occupied' : 'available'}`;
      if (isSelected) className += ' selected';

      return (
        <button
          key={seatId}
          className={className}
          onClick={() => toggleSeat(zone, rowNum, seatNum)}
          disabled={!isAdmin && isOccupied}
        >
          {seatNum}
        </button>
      );
    });
  };

  // Партер Сектори A, B, C (Ряди 2-23, по 8 місць)
  const parterreRows = Array.from({ length: 22 }, (_, i) => i + 2);
  
  // Бічні балкони (Ряди 1-19, по 3 місця)
  const sideBalconyRows = Array.from({ length: 19 }, (_, i) => i + 1);

  // Головний балкон (Різна кількість місць)
  const mainBalconyConfig = [
    { row: 1, seats: 26 }, { row: 2, seats: 29 }, { row: 3, seats: 28 },
    { row: 4, seats: 29 }, { row: 5, seats: 30 }, { row: 6, seats: 33 }
  ];

  return (
    <div className={`hall-wrapper ${isAdmin ? 'admin-mode' : ''}`}>
      <h2>АКТОВА ЗАЛА {isAdmin ? '(АДМІН)' : ''}</h2>
      
      <div className="scroll-container">
        <div className="hall-map">
          
          <div className="stage-container">
            <div className="stage">СЦЕНА</div>
          </div>

          {/* ПАРТЕР (A, B, C) */}
          <div className="zone-title">СЕКТОРИ A, B, C</div>
          <div className="parterre-abc">
            {parterreRows.map(row => (
              <div key={`abc-${row}`} className="row-wrapper">
                <span className="row-label">{row}</span>
                <div className="seats-group">{renderRow('A', row, 8)}</div>
                <div className="aisle-spacer"></div>
                <div className="seats-group">{renderRow('B', row, 8)}</div>
                <div className="aisle-spacer"></div>
                <div className="seats-group">{renderRow('C', row, 8)}</div>
                <span className="row-label">{row}</span>
              </div>
            ))}
          </div>

          {/* СЕКТОР D (Ряди 24-28) */}
          <div className="zone-title" style={{marginTop: '30px'}}>СЕКТОР D</div>
          <div className="parterre-d">
            <div className="row-wrapper">
              <span className="row-label">24</span>
              <div className="seats-group">{renderRow('D', 24, 26)}</div>
              <span className="row-label">24</span>
            </div>
            {[25, 26, 27, 28].map(row => (
              <div key={`d-${row}`} className="row-wrapper">
                <span className="row-label">{row}</span>
                {/* Центруємо 20 місць відносно 26 */}
                <div className="seats-group" style={{ padding: '0 80px' }}>
                  {renderRow('D', row, 20)}
                </div>
                <span className="row-label">{row}</span>
              </div>
            ))}
          </div>

          {/* БАЛКОНИ */}
          <div className="balconies-section">
            
            {/* Лівий бічний балкон */}
            <div className="side-balcony">
              <div className="zone-title small">БІЧНИЙ БАЛКОН (ЛІВИЙ)</div>
              {sideBalconyRows.map(row => (
                <div key={`lb-${row}`} className="row-wrapper">
                  <span className="row-label">{row}</span>
                  <div className="seats-group">{renderRow('ЛБ', row, 3)}</div>
                </div>
              ))}
            </div>

            {/* Головний балкон */}
            <div className="main-balcony">
              <div className="zone-title">ГОЛОВНИЙ БАЛКОН</div>
              {mainBalconyConfig.map(config => (
                <div key={`mb-${config.row}`} className="row-wrapper">
                  <span className="row-label">{config.row}</span>
                  <div className="seats-group justify-center">{renderRow('Балкон', config.row, config.seats)}</div>
                  <span className="row-label">{config.row}</span>
                </div>
              ))}
            </div>

            {/* Правий бічний балкон */}
            <div className="side-balcony">
              <div className="zone-title small">БІЧНИЙ БАЛКОН (ПРАВИЙ)</div>
              {sideBalconyRows.map(row => (
                <div key={`pb-${row}`} className="row-wrapper">
                  <div className="seats-group">{renderRow('ПБ', row, 3)}</div>
                  <span className="row-label">{row}</span>
                </div>
              ))}
            </div>

          </div>

        </div>
      </div>

      {/* ЛЕГЕНДА */}
      <div className="legend">
        <div className="legend-item"><span className="seat available legend-dot"></span> Вільне</div>
        <div className="legend-item"><span className="seat occupied legend-dot"></span> Зайняте/Бронь</div>
        <div className="legend-item"><span className="seat selected legend-dot"></span> Обране</div>
      </div>
    </div>
  );
}

export default App;