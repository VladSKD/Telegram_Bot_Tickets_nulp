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
        ? `ДІЗНАТИСЯ ІНФО (${selectedSeats[0].id})` 
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
    
    if (queryParams.get('admin') === 'true') setIsAdmin(true);
    if (queryParams.get('ev_id')) setEventId(queryParams.get('ev_id'));

    const handleMainButtonClick = () => {
      const dataToSend = selectedSeatsRef.current;
      if (dataToSend.length > 0) {
        if (isAdmin) {
          tg.sendData(`admin_seat|${eventId}|${dataToSend[0].id}`);
        } else {
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

  const toggleSeat = (zone, rowOrBox, seatNum) => {
    const seatId = `${zone}-${rowOrBox}-${seatNum}`;
    const isOccupied = occupiedSeats.includes(seatId);

    if (isAdmin) {
      if (!isOccupied) return;
      setSelectedSeats(prev => prev.some(s => s.id === seatId) ? [] : [{ id: seatId, zone, row: rowOrBox, seat: seatNum }]);
    } else {
      if (isOccupied) return;
      setSelectedSeats(prev => {
        if (prev.some(s => s.id === seatId)) return prev.filter(s => s.id !== seatId);
        return [...prev, { id: seatId, zone, row: rowOrBox, seat: seatNum }];
      });
    }
  };

  const renderSeats = (zone, rowOrBox, seatCount, startFrom = 1) => {
    return Array.from({ length: seatCount }).map((_, i) => {
      const seatNum = startFrom + i;
      const seatId = `${zone}-${rowOrBox}-${seatNum}`;
      const isOccupied = occupiedSeats.includes(seatId);
      const isSelected = selectedSeats.some(s => s.id === seatId);

      let className = `seat ${isOccupied ? 'occupied' : 'available'}`;
      if (isSelected) className += ' selected';
      if (zone === 'Ложа Л' || zone === 'Ложа П') className += ' box-seat';

      return (
        <button
          key={seatId}
          className={className}
          onClick={() => toggleSeat(zone, rowOrBox, seatNum)}
          disabled={!isAdmin && isOccupied}
        >
          {seatNum}
        </button>
      );
    });
  };

  // Партер: ряди 1-20. Зробимо масив від 20 до 1, щоб сцена була внизу.
  const parterreRows = Array.from({ length: 20 }, (_, i) => 20 - i);

  return (
    <div className={`hall-wrapper ${isAdmin ? 'admin-mode' : ''}`}>
      <h2>ОПЕРНИЙ БУДИНОК {isAdmin ? '(АДМІН)' : ''}</h2>
      
      <div className="scroll-container">
        <div className="opera-layout">
          
          {/* ЯРУСИ БАЛКОНІВ (Верхня частина, вигнуті) */}
          <div className="balconies-section">
            <div className="balcony-tier tier-3">
              <div className="zone-title">БАЛКОН 3</div>
              {[5, 4, 3, 2, 1].map(row => (
                <div key={`b3-${row}`} className={`row-wrapper curve-${row}`}>
                  <span className="row-label">{row}</span>
                  <div className="seats-group">{renderSeats('Б3', row, 30)}</div>
                  <span className="row-label">{row}</span>
                </div>
              ))}
            </div>

            <div className="balcony-tier tier-2">
              <div className="zone-title">БАЛКОН 2</div>
              {[5, 4, 3, 2, 1].map(row => (
                <div key={`b2-${row}`} className={`row-wrapper curve-${row}`}>
                  <span className="row-label">{row}</span>
                  <div className="seats-group">{renderSeats('Б2', row, 26)}</div>
                  <span className="row-label">{row}</span>
                </div>
              ))}
            </div>

            <div className="balcony-tier tier-1">
              <div className="zone-title">БАЛКОН 1</div>
              {[5, 4, 3, 2, 1].map(row => (
                <div key={`b1-${row}`} className={`row-wrapper curve-${row}`}>
                  <span className="row-label">{row}</span>
                  <div className="seats-group">{renderSeats('Б1', row, 24)}</div>
                  <span className="row-label">{row}</span>
                </div>
              ))}
            </div>
          </div>

          {/* ОСНОВНИЙ ПОВЕРХ: Ложі по боках, Партер по центру */}
          <div className="main-floor-section">
            
            {/* ЛІВІ ЛОЖІ */}
            <div className="boxes-column left-boxes">
              <div className="zone-title small">ЛОЖІ</div>
              {[14, 12, 10, 8, 6, 4, 2].map(boxNum => (
                <div key={`box-l-${boxNum}`} className="box-wrapper left-step">
                  <span className="box-number">{boxNum}</span>
                  <div className="seats-group box-grid">{renderSeats('Ложа Л', boxNum, 4)}</div>
                </div>
              ))}
            </div>

            {/* ПАРТЕР */}
            <div className="parterre-section">
              <div className="zone-title">ПАРТЕР</div>
              {parterreRows.map(row => {
                // Нижні ряди (ближче до сцени) вужчі
                const isFront = row <= 11;
                const sideCount = isFront ? 3 : 5;
                const centerCount = isFront ? 10 : 14;
                const rightStart = sideCount + centerCount + 1;

                return (
                  <div key={`p-${row}`} className="row-wrapper">
                    <span className="row-label">{row}</span>
                    
                    <div className="seats-group side-seats">
                      {renderSeats('П-Лівий', row, sideCount)}
                    </div>
                    
                    <div className="aisle"></div>
                    
                    <div className="seats-group">
                      {renderSeats('П-Центр', row, centerCount, sideCount + 1)}
                    </div>
                    
                    <div className="aisle"></div>
                    
                    <div className="seats-group side-seats">
                      {renderSeats('П-Правий', row, sideCount, rightStart)}
                    </div>

                    <span className="row-label">{row}</span>
                  </div>
                );
              })}
            </div>

            {/* ПРАВІ ЛОЖІ */}
            <div className="boxes-column right-boxes">
              <div className="zone-title small">ЛОЖІ</div>
              {[13, 11, 9, 7, 5, 3, 1].map(boxNum => (
                <div key={`box-r-${boxNum}`} className="box-wrapper right-step">
                  <div className="seats-group box-grid">{renderSeats('Ложа П', boxNum, 4)}</div>
                  <span className="box-number">{boxNum}</span>
                </div>
              ))}
            </div>

          </div>

          {/* СЦЕНА */}
          <div className="stage-container">
            <div className="stage">СЦЕНА</div>
          </div>

        </div>
      </div>

      {/* ЛЕГЕНДА */}
      <div className="legend">
        <div className="legend-item"><span className="seat available legend-dot"></span> Вільне</div>
        <div className="legend-item"><span className="seat occupied legend-dot"></span> Зайняте</div>
        <div className="legend-item"><span className="seat selected legend-dot"></span> Обране</div>
      </div>
    </div>
  );
}