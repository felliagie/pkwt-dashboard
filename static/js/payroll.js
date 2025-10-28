// Payroll Slip Export Functions

// Export to PDF
function exportToPDF() {
    const element = document.getElementById('payroll-slip');
    const { jsPDF } = window.jspdf;

    // Show loading state
    const originalContent = event.target.innerHTML;
    event.target.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2 inline" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Generating...';
    event.target.disabled = true;

    html2canvas(element, {
        scale: 2,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff'
    }).then(canvas => {
        const imgData = canvas.toDataURL('image/png');
        const pdf = new jsPDF('p', 'mm', 'a4');

        const imgWidth = 210; // A4 width in mm
        const pageHeight = 297; // A4 height in mm
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        let heightLeft = imgHeight;
        let position = 0;

        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;

        while (heightLeft >= 0) {
            position = heightLeft - imgHeight;
            pdf.addPage();
            pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
            heightLeft -= pageHeight;
        }

        pdf.save('Payroll_Slip_Jein_Lumempouw.pdf');

        // Reset button
        event.target.innerHTML = originalContent;
        event.target.disabled = false;
    }).catch(error => {
        console.error('Error generating PDF:', error);
        alert('Error generating PDF. Please try again.');
        event.target.innerHTML = originalContent;
        event.target.disabled = false;
    });
}

// Export to PNG
function exportToPNG() {
    const element = document.getElementById('payroll-slip');

    // Show loading state
    const originalContent = event.target.innerHTML;
    event.target.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2 inline" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Generating...';
    event.target.disabled = true;

    html2canvas(element, {
        scale: 3,
        useCORS: true,
        logging: false,
        backgroundColor: '#ffffff'
    }).then(canvas => {
        canvas.toBlob(blob => {
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'Payroll_Slip_Jein_Lumempouw.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);

            // Reset button
            event.target.innerHTML = originalContent;
            event.target.disabled = false;
        });
    }).catch(error => {
        console.error('Error generating PNG:', error);
        alert('Error generating PNG. Please try again.');
        event.target.innerHTML = originalContent;
        event.target.disabled = false;
    });
}

// Export to Excel
function exportToExcel() {
    // Show loading state
    const originalContent = event.target.innerHTML;
    event.target.innerHTML = '<svg class="animate-spin h-5 w-5 mr-2 inline" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>Generating...';
    event.target.disabled = true;

    try {
        // Create workbook
        const wb = XLSX.utils.book_new();

        // Prepare data
        const data = [
            ['PT JMAX INDONESIA'],
            ['Payroll Slip'],
            [''],
            ['EMPLOYEE INFORMATION'],
            ['Name', 'Jein Lumempouw'],
            ['ID', 'M25091060'],
            ['Position', 'BA PIXY Palu'],
            ['Client', 'PT. Mandom Indonesia'],
            [''],
            ['PAYMENT INFORMATION'],
            ['Payment Date', '31-Oct-25'],
            ['Tax Code', 'TK / 0'],
            ['Work Days', '25'],
            ['Bank Account', 'BRI (043401014645502)'],
            [''],
            ['EARNINGS', 'Amount'],
            ['Basic Salary', 3617000],
            ['KSD', 0],
            ['Incentive', 2100000],
            ['TDK', 0],
            ['Potongan Absensi', -602833],
            ['Tunjangan Pajak', 0],
            ['TOTAL EARNINGS', 5114167],
            [''],
            ['DEDUCTIONS', 'Amount'],
            ['JHT 2%', 72340],
            ['JP 1%', 36170],
            ['BPJS Kesehatan 1%', 36170],
            ['PPH21', 0],
            ['TOTAL DEDUCTIONS', 144680],
            [''],
            ['TAKE HOME PAY', 4969487],
            [''],
            ['Generated Date', new Date().toLocaleDateString('en-GB')],
            ['Approved By', 'Fitria Nurhafsyah - HR Payroll & Operation']
        ];

        // Create worksheet
        const ws = XLSX.utils.aoa_to_sheet(data);

        // Set column widths
        ws['!cols'] = [
            { wch: 25 },
            { wch: 20 }
        ];

        // Style header rows (bold)
        const headerRows = [0, 1, 3, 9, 15, 24, 31];
        headerRows.forEach(row => {
            const cellRef = XLSX.utils.encode_cell({ r: row, c: 0 });
            if (ws[cellRef]) {
                ws[cellRef].s = {
                    font: { bold: true }
                };
            }
        });

        // Add worksheet to workbook
        XLSX.utils.book_append_sheet(wb, ws, 'Payroll Slip');

        // Generate Excel file
        XLSX.writeFile(wb, 'Payroll_Slip_Jein_Lumempouw.xlsx');

        // Reset button
        event.target.innerHTML = originalContent;
        event.target.disabled = false;
    } catch (error) {
        console.error('Error generating Excel:', error);
        alert('Error generating Excel. Please try again.');
        event.target.innerHTML = originalContent;
        event.target.disabled = false;
    }
}

// Print function as alternative PDF export
function printPayrollSlip() {
    window.print();
}

// Add print styles dynamically
const style = document.createElement('style');
style.textContent = `
    @media print {
        body {
            background: white;
            padding: 0;
        }
        .print\\:hidden {
            display: none !important;
        }
        #payroll-slip {
            box-shadow: none;
            border-radius: 0;
            margin: 0;
            padding: 20px;
        }
    }
`;
document.head.appendChild(style);
