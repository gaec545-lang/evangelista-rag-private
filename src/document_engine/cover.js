const { Paragraph, TextRun, ImageRun, AlignmentType, PageBreak, BorderStyle } = require('docx');
const fs = require('fs');
const path = require('path');

/**
 * Genera la sección de portada de un documento Evangelista & Co.
 * @param {Object} config - Configuración de la portada
 */
const buildCoverPage = (config) => {
  const {
    docType,         // 'PROPUESTA COMERCIAL', 'CONTRATO', etc.
    projectName,     // Nombre del proyecto
    clientName,      // Nombre del cliente
    clientContact,   // Nombre y cargo del contacto
    folio,           // EVA-HTD-P-26-001
    date,            // 'Puebla, Pue. · Abr 2026'
    accentColor,     // '#c05538' | '#534ab7' | '#4a5c3a' | '#0f6e56'
    isConfidential = true,
    isInternal = false,
  } = config;

  // Convertir hex a RGB para docx
  const hexToDocxColor = (hex) => hex.replace('#', '').toUpperCase();
  const accent = hexToDocxColor(accentColor || '#c05538');

  // Logo PNG → base64
  let logoRun = null;
  try {
    const logoPath = path.join(__dirname, 'assets/logoEvangelistaCo.png');
    if (fs.existsSync(logoPath)) {
      const logoData = fs.readFileSync(logoPath);
      logoRun = new ImageRun({
        data: logoData,
        type: 'png',
        transformation: { width: 80, height: 80 },
      });
    }
  } catch (e) {
    console.warn("Logo no encontrado, omitiendo...");
  }

  const children = [
    // Espacio superior
    new Paragraph({ spacing: { before: 0, after: 480 }, children: [] }),

    // Logo centrado
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 360 },
      children: logoRun ? [logoRun] : [],
    }),

    // EVANGELISTA & CO.
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 80 },
      children: [
        new TextRun({
          text: 'EVANGELISTA & CO.',
          font: 'Instrument Serif',
          size: 32,           // 16pt
          bold: true,
          color: '1A1A1A',
        }),
      ],
    }),

    // Tagline
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 960 },
      children: [
        new TextRun({
          text: 'ESTRATEGIA · INTELIGENCIA · RESULTADOS',
          font: 'Inter',
          size: 18,           // 9pt
          color: '666666',
          // characterSpacing is not directly supported in all docx versions without custom XML but we can try
        }),
      ],
    }),

    // Tipo de documento — grande, centrado, acento de color
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 240 },
      border: {
        bottom: { style: BorderStyle.NONE },
      },
      children: [
        new TextRun({
          text: (docType || 'DOCUMENTO').toUpperCase(),
          font: 'Instrument Serif',
          size: 52,           // 26pt
          bold: true,
          color: accent,
        }),
      ],
    }),

    // Nombre del proyecto
    ...(projectName ? [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 1440 },
        children: [
          new TextRun({
            text: projectName,
            font: 'Inter',
            size: 24,         // 12pt
            color: '444444',
            italics: true,
          }),
        ],
      }),
    ] : [new Paragraph({ spacing: { before: 0, after: 1440 }, children: [] })]),

    // Línea separadora con color de acento
    new Paragraph({
      spacing: { before: 0, after: 240 },
      border: {
        bottom: {
          style: BorderStyle.SINGLE,
          size: 12,           // 1.5pt
          color: accent,
          space: 1,
        },
      },
      children: [],
    }),

    // Badge interno (solo si isInternal)
    ...(isInternal ? [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 120, after: 240 },
        children: [
          new TextRun({
            text: '⚠ USO INTERNO · No entregar al cliente',
            font: 'Inter',
            size: 16,
            color: 'B8860B',
            bold: true,
          }),
        ],
      }),
    ] : []),

    // Bloque de metadatos — tabla de 2 columnas
    new Paragraph({
      spacing: { before: 240, after: 80 },
      children: [
        new TextRun({ text: 'Preparado para:  ', font: 'Inter', size: 20, color: '666666' }),
        new TextRun({ text: clientName || '', font: 'Inter', size: 20, bold: true, color: '1A1A1A' }),
      ],
    }),

    ...(clientContact ? [
      new Paragraph({
        spacing: { before: 0, after: 80 },
        children: [
          new TextRun({ text: 'Contacto:          ', font: 'Inter', size: 20, color: '666666' }),
          new TextRun({ text: clientContact, font: 'Inter', size: 20, color: '1A1A1A' }),
        ],
      }),
    ] : []),

    new Paragraph({
      spacing: { before: 120, after: 80 },
      children: [
        new TextRun({ text: 'Folio:               ', font: 'Inter', size: 20, color: '666666' }),
        new TextRun({ text: folio || '', font: 'Inter', size: 20, bold: true, color: accent }),
      ],
    }),

    new Paragraph({
      spacing: { before: 0, after: 240 },
      children: [
        new TextRun({ text: 'Fecha:              ', font: 'Inter', size: 20, color: '666666' }),
        new TextRun({ text: date || '', font: 'Inter', size: 20, color: '1A1A1A' }),
      ],
    }),

    // Footer de confidencialidad
    new Paragraph({
      spacing: { before: 480, after: 0 },
      children: [
        new TextRun({
          text: isInternal
            ? 'Documento de Uso Interno · Propiedad de Evangelista & Co. · 2026'
            : 'Documento Confidencial · Propiedad de Evangelista & Co. · 2026',
          font: 'Inter',
          size: 16,
          color: '999999',
          italics: true,
        }),
      ],
    }),

    // Salto de página — termina la portada
    new Paragraph({
      children: [new PageBreak()],
    }),
  ];

  return children;
};

module.exports = { buildCoverPage };
