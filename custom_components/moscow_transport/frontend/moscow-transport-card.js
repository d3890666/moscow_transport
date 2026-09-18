/**
 * Moscow Transport Lovelace Card for Home Assistant
 * Modern real-time transit departure board with manual refresh button.
 */

class MoscowTransportCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity (e.g. sensor.rublevskoe_shosse_14_moscow_transport)');
    }
    this._config = {
      title: config.title || '',
      max_items: config.max_items || 6,
      show_empty: config.show_empty !== false,
      show_refresh: config.show_refresh !== false,
      ...config
    };
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement('moscow-transport-card-editor');
  }

  static getStubConfig() {
    return {
      entity: '',
      title: 'Московский транспорт',
      max_items: 6,
      show_refresh: true
    };
  }

  render() {
    if (!this._hass || !this._config) return;

    const entityId = this._config.entity;
    const stateObj = this._hass.states[entityId];

    if (!stateObj) {
      this.shadowRoot.innerHTML = `
        <ha-card style="padding: 16px; color: var(--error-color, red);">
          Сущность <b>${entityId}</b> не найдена.
        </ha-card>
      `;
      return;
    }

    const attrs = stateObj.attributes || {};
    const stopName = this._config.title || attrs.stop_name || stateObj.attributes.friendly_name || 'Остановка';
    const allArrivals = attrs.all_arrivals || [];

    // Fallback if all_arrivals not present (e.g. legacy attributes)
    let arrivals = [...allArrivals];
    if (arrivals.length === 0 && attrs) {
      Object.keys(attrs).forEach(key => {
        if (Array.isArray(attrs[key]) && key !== 'all_arrivals') {
          attrs[key].forEach(item => {
            const isTelemetry = !item.endsWith('*');
            arrivals.push({
              route: key,
              time_formatted: item,
              by_telemetry: isTelemetry ? 1 : 0,
              time_seconds: 99999
            });
          });
        }
      });
    }

    // Limit arrivals
    const displayArrivals = arrivals.slice(0, this._config.max_items);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          padding: 18px;
          background: var(--ha-card-background, var(--card-background-color, #fff));
          border-radius: var(--ha-card-border-radius, 16px);
          box-shadow: var(--ha-card-box-shadow, 0 4px 12px rgba(0,0,0,0.06));
          font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
          overflow: hidden;
        }
        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }
        .header-title-wrap {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .icon-badge {
          width: 38px;
          height: 38px;
          border-radius: 10px;
          background: linear-gradient(135deg, #0077ff, #0055c4);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          box-shadow: 0 4px 10px rgba(0, 119, 255, 0.3);
          flex-shrink: 0;
        }
        .icon-badge svg {
          width: 22px;
          height: 22px;
          fill: currentColor;
        }
        .title {
          font-size: 1.15rem;
          font-weight: 600;
          color: var(--primary-text-color);
          line-height: 1.2;
        }
        .subtitle {
          font-size: 0.8rem;
          color: var(--secondary-text-color);
          margin-top: 2px;
        }
        .refresh-btn {
          background: none;
          border: none;
          width: 36px;
          height: 36px;
          border-radius: 50%;
          cursor: pointer;
          color: var(--secondary-text-color);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: color 0.2s, background 0.2s, transform 0.2s;
          outline: none;
          flex-shrink: 0;
        }
        .refresh-btn:hover {
          color: var(--primary-color, #0077ff);
          background: var(--primary-color-opacity, rgba(0, 119, 255, 0.08));
        }
        .refresh-btn:active {
          transform: scale(0.92);
        }
        .refresh-btn svg {
          width: 20px;
          height: 20px;
          fill: currentColor;
        }
        .refresh-btn.spinning svg {
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .arrivals-list {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .arrival-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 14px;
          background: var(--secondary-background-color, #f7f9fa);
          border-radius: 12px;
          transition: transform 0.15s ease, background 0.15s ease;
        }
        .arrival-item:hover {
          background: var(--primary-color-opacity, rgba(0, 119, 255, 0.06));
          transform: translateX(2px);
        }
        .route-badge {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-width: 44px;
          padding: 4px 8px;
          border-radius: 8px;
          font-weight: 700;
          font-size: 1.05rem;
          background: #e30613;
          color: white;
          letter-spacing: 0.5px;
          box-shadow: 0 2px 6px rgba(227, 6, 19, 0.25);
        }
        .route-badge.bus {
          background: #0077ff;
          box-shadow: 0 2px 6px rgba(0, 119, 255, 0.25);
        }
        .route-info {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .time-wrap {
          text-align: right;
          display: flex;
          flex-direction: column;
          align-items: flex-end;
        }
        .eta-main {
          font-size: 1.15rem;
          font-weight: 700;
          color: var(--primary-text-color);
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .telemetry-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background-color: #00c853;
          box-shadow: 0 0 8px #00c853;
          display: inline-block;
          animation: pulse 2s infinite;
        }
        .schedule-icon {
          font-size: 0.75rem;
          color: var(--secondary-text-color);
        }
        .eta-clock {
          font-size: 0.8rem;
          color: var(--secondary-text-color);
          margin-top: 1px;
        }
        .empty-state {
          padding: 24px;
          text-align: center;
          color: var(--secondary-text-color);
          font-size: 0.95rem;
        }
        @keyframes pulse {
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.85); }
          100% { opacity: 1; transform: scale(1); }
        }
      </style>

      <ha-card>
        <div class="header">
          <div class="header-title-wrap">
            <div class="icon-badge">
              <svg viewBox="0 0 24 24">
                <path d="M4,16C4,16.88 4.39,17.67 5,18.22V20A1,1 0 0,0 6,21H7A1,1 0 0,0 8,20V19H16V20A1,1 0 0,0 17,21H18A1,1 0 0,0 19,20V18.22C19.61,17.67 20,16.88 20,16V6C20,2.5 16.42,2 12,2C7.58,2 4,2.5 4,6V16M6.5,17A1.5,1.5 0 0,1 5,15.5A1.5,1.5 0 0,1 6.5,14A1.5,1.5 0 0,1 8,15.5A1.5,1.5 0 0,1 6.5,17M17.5,17A1.5,1.5 0 0,1 16,15.5A1.5,1.5 0 0,1 17.5,14A1.5,1.5 0 0,1 19,15.5A1.5,1.5 0 0,1 17.5,17M5,11V6H19V11H5Z" />
              </svg>
            </div>
            <div>
              <div class="title">${stopName}</div>
              <div class="subtitle">Онлайн табло прибытия</div>
            </div>
          </div>
          ${this._config.show_refresh ? `
            <button class="refresh-btn" id="refresh-button" title="Принудительно обновить расписание">
              <svg viewBox="0 0 24 24">
                <path d="M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z" />
              </svg>
            </button>
          ` : ''}
        </div>

        ${displayArrivals.length === 0 ? `
          <div class="empty-state">
            Сейчас нет данных о приближающемся транспорте
          </div>
        ` : `
          <div class="arrivals-list">
            ${displayArrivals.map(item => {
              const minutes = item.minutes !== undefined ? item.minutes : null;
              const isTelemetry = item.by_telemetry === 1;
              const etaDisplay = minutes !== null
                ? (minutes === 0 ? 'Прибывает' : `${minutes} мин`)
                : item.time_formatted;

              return `
                <div class="arrival-item">
                  <div class="route-info">
                    <span class="route-badge bus">${item.route}</span>
                  </div>
                  <div class="time-wrap">
                    <div class="eta-main">
                      ${isTelemetry ? '<span class="telemetry-dot" title="Живая GPS телеметрия"></span>' : '<span class="schedule-icon" title="По расписанию">🕒</span>'}
                      <span>${etaDisplay}</span>
                    </div>
                    ${item.time_formatted ? `<div class="eta-clock">${item.time_formatted}</div>` : ''}
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `}
      </ha-card>
    `;

    const refreshBtn = this.shadowRoot.querySelector('#refresh-button');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        refreshBtn.classList.add('spinning');
        try {
          await this._hass.callService('homeassistant', 'update_entity', {
            entity_id: entityId
          });
        } catch (err) {
          console.warn('Failed to force update entity:', err);
        } finally {
          setTimeout(() => {
            refreshBtn.classList.remove('spinning');
          }, 800);
        }
      });
    }
  }
}

class MoscowTransportCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  render() {
    if (!this._hass || !this._config) return;

    // Filter available moscow_transport sensors
    const entities = Object.keys(this._hass.states).filter(
      e => e.startsWith('sensor.') && (e.includes('moscow_transport') || this._hass.states[e].attributes.attribution?.includes('Московского транспорта'))
    );

    this.innerHTML = `
      <div style="display: flex; flex-direction: column; gap: 14px; padding: 12px 0;">
        <div>
          <label style="display:block; margin-bottom: 4px; font-weight: 500;">Сущность сенсора остановки:</label>
          <select id="entity-select" style="width: 100%; padding: 8px; border-radius: 8px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, #fff); color: var(--primary-text-color);">
            <option value="">Выберите сенсор</option>
            ${entities.map(e => `<option value="${e}" ${this._config.entity === e ? 'selected' : ''}>${this._hass.states[e].attributes.friendly_name || e} (${e})</option>`).join('')}
          </select>
        </div>
        <div>
          <label style="display:block; margin-bottom: 4px; font-weight: 500;">Заголовок карточки (опционально):</label>
          <input type="text" id="title-input" value="${this._config.title || ''}" placeholder="По умолчанию название остановки" style="width: 100%; padding: 8px; border-radius: 8px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, #fff); color: var(--primary-text-color);" />
        </div>
        <div>
          <label style="display:block; margin-bottom: 4px; font-weight: 500;">Максимум рейсов на табло:</label>
          <input type="number" id="max-items-input" min="1" max="20" value="${this._config.max_items || 6}" style="width: 100%; padding: 8px; border-radius: 8px; border: 1px solid var(--divider-color, #ccc); background: var(--card-background-color, #fff); color: var(--primary-text-color);" />
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <input type="checkbox" id="refresh-checkbox" ${this._config.show_refresh !== false ? 'checked' : ''} style="width: 18px; height: 18px;" />
          <label for="refresh-checkbox" style="font-weight: 500; cursor: pointer;">Показывать кнопку принудительного обновления</label>
        </div>
      </div>
    `;

    this.querySelector('#entity-select').addEventListener('change', (ev) => {
      this._config = { ...this._config, entity: ev.target.value };
      this.fireConfigChanged();
    });

    this.querySelector('#title-input').addEventListener('input', (ev) => {
      this._config = { ...this._config, title: ev.target.value };
      this.fireConfigChanged();
    });

    this.querySelector('#max-items-input').addEventListener('change', (ev) => {
      this._config = { ...this._config, max_items: parseInt(ev.target.value, 10) || 6 };
      this.fireConfigChanged();
    });

    this.querySelector('#refresh-checkbox').addEventListener('change', (ev) => {
      this._config = { ...this._config, show_refresh: ev.target.checked };
      this.fireConfigChanged();
    });
  }

  fireConfigChanged() {
    const event = new CustomEvent('config-changed', {
      detail: { config: this._config },
      bubbles: true,
      composed: true
    });
    this.dispatchEvent(event);
  }
}

customElements.define('moscow-transport-card', MoscowTransportCard);
customElements.define('moscow-transport-card-editor', MoscowTransportCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'moscow-transport-card',
  name: 'Moscow Transport Board',
  description: 'Табло прибытия общественного транспорта Москвы с поддержкой GPS телеметрии и расписания',
  preview: true
});

console.info(
  '%c МОСКОВСКИЙ ТРАНСПОРТ %c v26.09.02 ',
  'color: white; background: #0077ff; font-weight: 700;',
  'color: #0077ff; background: #e6f2ff; font-weight: 700;'
);
