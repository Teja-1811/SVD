function viewInvoice(billId) {
    // Open PDF in new tab
    window.open(`/milk_agency/generate-invoice-pdf/${billId}/`, '_blank');
}

function downloadInvoice(billId) {
    // Create a temporary link to download the PDF
    const link = document.createElement('a');
    link.href = `/milk_agency/generate-invoice-pdf/${billId}/`;
    link.download = `invoice_${billId}.pdf`;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
