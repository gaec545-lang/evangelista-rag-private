const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, WidthType, BorderStyle, ShadingType } = require('docx');
const fs = require('fs');
const path = require('path');
const { buildCoverPage } = require('../cover');
const { buildPageHeader, buildPageFooter } = require('../header_footer');

const args = process.argv.slice(2);
if (args.length < 2) {
  console.error("Uso: node acta_entrega.js '<json_payload>' <output_path>");
  process.exit(1);
}

const payload = JSON.parse(args[0]);
const outputPath = args[1];

// Configuración de Identidad
payload.docType = 'ACTA DE ENTREGA DE ACTIVOS';
const accent = (payload.accentColor || '#0f6e56').replace('#', '');

const doc = new Document({
  sections: [
    {
      properties: {},
      children: buildCoverPage(payload),
    },
    {
      properties: {
        page: {
          pageNumbers: { start: 1, formatType: "DECIMAL" }
        }
      },
      headers: buildPageHeader(payload),
      footers: buildPageFooter(payload),
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 240, after: 360 },
          children: [
            new TextRun({
              text: 'ACTA DE ENTREGA Y CIERRE DE PROYECTO',
              font: 'Instrument Serif',
              size: 32,
              bold: true,
              color: accent,
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({
              text: `En la ciudad de ${payload.city || 'Puebla, Pue.'}, siendo el día ${payload.close_date || new Date().toLocaleDateString('es-MX')}, se hace constar la entrega formal de los activos de decisión generados durante el proyecto `,
              font: 'Inter',
              size: 22,
            }),
            new TextRun({
              text: `"${payload.project_name || 'Proyecto'}"`,
              font: 'Inter',
              size: 22,
              bold: true,
            }),
            new TextRun({
              text: ` por parte de `,
              font: 'Inter',
              size: 22,
            }),
            new TextRun({
              text: 'Evangelista & Co.',
              font: 'Inter',
              size: 22,
              bold: true,
            }),
            new TextRun({
              text: ' al cliente ',
              font: 'Inter',
              size: 22,
            }),
            new TextRun({
              text: `${payload.client_name || 'Cliente'}.`,
              font: 'Inter',
              size: 22,
              bold: true,
            }),
          ]
        }),

        // Tabla de Activos Entregados
        new Paragraph({
          spacing: { before: 240, after: 120 },
          children: [
            new TextRun({
              text: '1. ACTIVOS ENTREGADOS',
              font: 'Inter',
              size: 18,
              bold: true,
              color: '444444',
            })
          ]
        }),

        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          borders: {
            top: { style: BorderStyle.SINGLE, size: 1, color: 'E0E0E0' },
            bottom: { style: BorderStyle.SINGLE, size: 1, color: 'E0E0E0' },
            left: { style: BorderStyle.SINGLE, size: 1, color: 'E0E0E0' },
            right: { style: BorderStyle.SINGLE, size: 1, color: 'E0E0E0' },
            insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: 'E0E0E0' },
          },
          rows: [
            new TableRow({
              children: [
                new TableCell({
                  width: { size: 70, type: WidthType.PERCENTAGE },
                  shading: { fill: 'F9F9F9', type: ShadingType.CLEAR },
                  children: [new Paragraph({ children: [new TextRun({ text: 'Descripción del Activo', font: 'Inter', size: 18, bold: true })] })]
                }),
                new TableCell({
                  width: { size: 30, type: WidthType.PERCENTAGE },
                  shading: { fill: 'F9F9F9', type: ShadingType.CLEAR },
                  children: [new Paragraph({ children: [new TextRun({ text: 'Formato', font: 'Inter', size: 18, bold: true })] })]
                }),
              ]
            }),
            ...(payload.deliverables || []).map(d => new TableRow({
              children: [
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: d.title, font: 'Inter', size: 18 })] })] }),
                new TableCell({ children: [new Paragraph({ children: [new TextRun({ text: d.type || 'Digital', font: 'Inter', size: 18 })] })] }),
              ]
            }))
          ]
        }),

        // Cláusula de Conformidad
        new Paragraph({
          spacing: { before: 360, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({
              text: '2. CONFORMIDAD Y CIERRE',
              font: 'Inter',
              size: 18,
              bold: true,
              color: '444444',
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({
              text: 'El Cliente manifiesta su total conformidad con los entregables recibidos y reconoce que los mismos cumplen con los objetivos estratégicos y técnicos planteados inicialmente. Con la firma de la presente, se da por concluido el compromiso operativo y se procede a la liberación de las garantías y compromisos de ambas partes.',
              font: 'Inter',
              size: 22,
            })
          ]
        }),

        // Firmas
        new Paragraph({ spacing: { before: 1440, after: 0 }, children: [] }),

        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          borders: {
            top: { style: BorderStyle.NONE },
            bottom: { style: BorderStyle.NONE },
            left: { style: BorderStyle.NONE },
            right: { style: BorderStyle.NONE },
            insideHorizontal: { style: BorderStyle.NONE },
            insideVertical: { style: BorderStyle.NONE },
          },
          rows: [
            new TableRow({
              children: [
                new TableCell({
                  children: [
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      border: { top: { style: BorderStyle.SINGLE, size: 1, color: '000000' } },
                      children: [
                        new TextRun({ text: payload.signer_name || 'Adriel Evangelista', font: 'Inter', size: 20, bold: true }),
                      ]
                    }),
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [
                        new TextRun({ text: 'Por Evangelista & Co.', font: 'Inter', size: 18, color: '666666' }),
                      ]
                    })
                  ]
                }),
                new TableCell({
                  children: [
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      border: { top: { style: BorderStyle.SINGLE, size: 1, color: '000000' } },
                      children: [
                        new TextRun({ text: payload.client_signer_name || 'Nombre del Cliente', font: 'Inter', size: 20, bold: true }),
                      ]
                    }),
                    new Paragraph({
                      alignment: AlignmentType.CENTER,
                      children: [
                        new TextRun({ text: `Por ${payload.client_name || 'El Cliente'}`, font: 'Inter', size: 18, color: '666666' }),
                      ]
                    })
                  ]
                }),
              ]
            })
          ]
        })
      ]
    }
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outputPath, buffer);
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
