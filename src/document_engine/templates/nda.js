const { Document, Packer, Paragraph, TextRun, AlignmentType } = require('docx');
const fs = require('fs');
const { buildCoverPage } = require('../cover');
const { buildPageHeader, buildPageFooter } = require('../header_footer');

const args = process.argv.slice(2);
const payload = JSON.parse(args[0]);
const outputPath = args[1];

payload.docType = 'CONVENIO DE CONFIDENCIALIDAD (NDA)';
const accent = (payload.accentColor || '#3e4d32').replace('#', ''); // Default to eva-olive

const doc = new Document({
  sections: [
    { children: buildCoverPage(payload) },
    {
      headers: buildPageHeader(payload),
      footers: buildPageFooter(payload),
      children: [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 240, after: 480 },
          children: [
            new TextRun({
              text: 'CONVENIO DE CONFIDENCIALIDAD Y NO DIVULGACIÓN',
              font: 'Times New Roman',
              size: 28,
              bold: true,
              color: accent,
            })
          ]
        }),
        new Paragraph({
          spacing: { before: 120, after: 240 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({
              text: `El presente convenio se celebra en la ciudad de Puebla, Pue., con fecha de `,
              font: 'Inter',
              size: 20,
            }),
            new TextRun({
              text: payload.date || 'hoy',
              font: 'Inter',
              size: 20,
              bold: true,
            }),
            new TextRun({
              text: `, entre `,
              font: 'Inter',
              size: 20,
            }),
            new TextRun({
              text: 'Evangelista & Co.',
              font: 'Inter',
              size: 20,
              bold: true,
            }),
            new TextRun({
              text: ' (en lo sucesivo "La Firma") y ',
              font: 'Inter',
              size: 20,
            }),
            new TextRun({
              text: payload.client_name || 'El Cliente',
              font: 'Inter',
              size: 20,
              bold: true,
            }),
            new TextRun({
              text: ' (en lo sucesivo "El Cliente"), al tenor de las siguientes:',
              font: 'Inter',
              size: 20,
            }),
          ]
        }),

        new Paragraph({
          spacing: { before: 240, after: 120 },
          children: [new TextRun({ text: 'DECLARACIONES', font: 'Inter', size: 22, bold: true, color: '666666' })]
        }),
        new Paragraph({
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({
              text: 'I. La Firma es una organización especializada en servicios de inteligencia estratégica y arquitectura operativa. II. El Cliente requiere compartir información técnica y financiera para la ejecución del proyecto ',
              font: 'Inter',
              size: 20,
            }),
            new TextRun({
              text: payload.project_name || 'especificado',
              font: 'Inter',
              size: 20,
              italics: true,
            }),
            new TextRun({
              text: '.',
              font: 'Inter',
              size: 20,
            }),
          ]
        }),

        new Paragraph({
          spacing: { before: 240, after: 120 },
          children: [new TextRun({ text: 'CLÁUSULAS', font: 'Inter', size: 22, bold: true, color: '666666' })]
        }),
        
        new Paragraph({
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({ text: 'PRIMERA. OBJETO. ', font: 'Inter', size: 20, bold: true }),
            new TextRun({ text: 'El presente instrumento tiene por objeto establecer los términos y condiciones bajo los cuales las partes protegerán la Información Confidencial intercambiada.', font: 'Inter', size: 20 }),
          ]
        }),

        new Paragraph({
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({ text: 'SEGUNDA. DEFINICIÓN. ', font: 'Inter', size: 20, bold: true }),
            new TextRun({ text: 'Se entiende por "Información Confidencial" todos los datos, estrategias, algoritmos, estados financieros y procesos operativos revelados en cualquier formato.', font: 'Inter', size: 20 }),
          ]
        }),

        new Paragraph({
          spacing: { before: 120, after: 120 },
          alignment: AlignmentType.JUSTIFY,
          children: [
            new TextRun({ text: 'TERCERA. OBLIGACIONES. ', font: 'Inter', size: 20, bold: true }),
            new TextRun({ text: 'Las partes se obligan a: (a) No divulgar a terceros la información recibida; (b) Utilizarla exclusivamente para los fines del proyecto; (c) Implementar medidas de seguridad razonables para su protección.', font: 'Inter', size: 20 }),
          ]
        }),

        new Paragraph({
          spacing: { before: 480, after: 120 },
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: 'FIRMANTES', font: 'Inter', size: 18, bold: true, color: '999999' })]
        }),

        new Paragraph({
          spacing: { before: 960, after: 120 },
          children: [
            new TextRun({ text: '__________________________          __________________________', font: 'Inter', size: 20 }),
          ]
        }),
        new Paragraph({
          children: [
            new TextRun({ text: '        Adriel Evangelista                              Por El Cliente', font: 'Inter', size: 18, bold: true }),
          ]
        }),
        new Paragraph({
          children: [
            new TextRun({ text: '        Director General                                Representante Legal', font: 'Inter', size: 16, color: '666666' }),
          ]
        }),
      ]
    }
  ]
});

Packer.toBuffer(doc).then(buffer => fs.writeFileSync(outputPath, buffer));
