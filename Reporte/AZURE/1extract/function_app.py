import azure.functions as func
import logging
import fitz
import os
from azure.storage.blob import BlobServiceClient
import re
import pandas as pd
from io import BytesIO

def read_pdf_from_blob(blob_client):

    # Download blob content as bytes
    blob_data = blob_client.download_blob().readall()

    # Use PyMuPDF to read the PDF content
    pdf_document = fitz.open("pdf", blob_data)
    
    # Extract text from the PDF
    pdf_text = ""
    for page_num in range(pdf_document.page_count):
        page = pdf_document[page_num]
        pdf_text += page.get_text()

    return pdf_text

def get_date(pdf_text):
        # Expresión regular para buscar una fecha en formato DD/MM/AAAA
        patron_fecha = r"\b\d{2}/\d{2}/\d{4}\b"
        try:
            fechas_encontradas = re.findall(patron_fecha, pdf_text)
            if fechas_encontradas:
                return max(fechas_encontradas)
        except FileNotFoundError:
            print(f"No se pudo encontrar el archivo")
        except Exception as e:
            print(f"Error al leer el archivo: {e}")

        return "-"

def get_content_between_words(pdf_text, palabra1, palabra2):
        pos_palabra1 = pdf_text.find(palabra1)
        if pos_palabra1 != -1:
            # Obtenemos el contenido después de la palabra1 hasta la palabra2
            pos_inicio = pos_palabra1 + len(palabra1)
            pos_fin = pdf_text.find(palabra2, pos_inicio)
            if pos_fin == -1:
                pos_fin = len(pdf_text)
            informacion = pdf_text[pos_inicio:pos_fin].strip()
            return informacion
        
def building_data(pdf_filename,pdf_content):
    data = {
        "ARCHIVO":[],
        "NOMBRE/RAZÓN": [],
        "DIRECCION": [],
        "CUPS": [],
        "ASESOR ENERGETICO": [],
        "FECHA": []
    }

    fecha_de_envio = get_date(pdf_content)
    data["FECHA"].append(fecha_de_envio) 

    if 'OPT' in pdf_filename or 'AHORRO' in pdf_filename:
        data["ARCHIVO"].append(pdf_filename)
        data["NOMBRE/RAZÓN"].append("-")
        data["DIRECCION"].append("-")
        data["CUPS"].append("-")
        data["ASESOR ENERGETICO"].append("-") 

    # Get info
    elif " GAS " in pdf_filename or pdf_content.find("GAS")!=-1:   
        # Read PDF from blob storage
        nombre_razon = get_content_between_words(pdf_content, "NOMBRE/RAZÓN\n", "\nDIRECCION")
        direccion = get_content_between_words(pdf_content, "DIRECCION", "CUPS")
        cups = get_content_between_words(pdf_content, "CUPS\n", "\n")
        
        data["ARCHIVO"].append(pdf_filename)
        data["NOMBRE/RAZÓN"].append(nombre_razon)
        data["DIRECCION"].append(direccion)
        data["CUPS"].append(cups)
        data["ASESOR ENERGETICO"].append(asesor)

    else:
        anual = pdf_content.lower().find("anual")
        actual = pdf_content.find("TOTAL FACTURA")
        
        dospuntozero=pdf_content.find("2.0TD")

        #2.0 completo
        if anual != -1 and actual != -1 and dospuntozero != -1:
            nombre_razon = get_content_between_words(pdf_content, "NOMBRE/RAZÓN", "DIRECCION")
            direccion = get_content_between_words(pdf_content, "DIRECCION\n", "\n")
            cups = get_content_between_words(pdf_content, "CUPS\n", "\n")
            asesor = get_content_between_words(pdf_content, "ASESOR ENERGETICO\n", "\n")

            data["ARCHIVO"].append(pdf_filename)
            data["NOMBRE/RAZÓN"].append(nombre_razon)
            data["DIRECCION"].append(direccion)
            data["CUPS"].append(cups)
            data["ASESOR ENERGETICO"].append(asesor)

        #2.0 actual        
        elif anual == -1 and actual != -1 and dospuntozero != -1:
            nombre_razon = get_content_between_words(pdf_content, "NOMBRE/RAZÓN", "DIRECCION")
            direccion = get_content_between_words(pdf_content, "DIRECCION\n", "\n")
            cups = get_content_between_words(pdf_content, "CUPS\n", "\nDATOS")
            asesor = get_content_between_words(pdf_content, "\n", "\nTOTAL POTENCIA")

            data["ARCHIVO"].append(pdf_filename)
            data["NOMBRE/RAZÓN"].append(nombre_razon)
            data["DIRECCION"].append(direccion)
            data["CUPS"].append(cups)
            data["ASESOR ENERGETICO"].append(asesor)

        #2.0 anual
        elif anual != -1 and actual == -1 and dospuntozero != -1:
            nombre_razon = get_content_between_words(pdf_content, "NOMBRE/RAZÓN", "DIRECCION")
            direccion = get_content_between_words(pdf_content, "DIRECCION\n", "\n")
            cups = get_content_between_words(pdf_content, "CUPS", "DATOS")
            
            #dealing with a particularity of this content
            asesor = get_content_between_words(pdf_content,"ESTIMADO\n", "@")
            pattern = r'\d+\s(.+)$'
            # Use re.search to find the first match in the string
            match = re.search(pattern, asesor)
            # Extract the matched text
            if match:
                asesor = match.group(1)

            data["ARCHIVO"].append(pdf_filename)
            data["NOMBRE/RAZÓN"].append(nombre_razon)
            data["DIRECCION"].append(direccion)
            data["CUPS"].append(cups)
            data["ASESOR ENERGETICO"].append(asesor)

        #3.0/6.x completo
        if anual != -1 and actual != -1 and dospuntozero == -1:
            nombre_razon = get_content_between_words(pdf_content, "NOMBRE/RAZÓN", "DIRECCION")
            direccion = get_content_between_words(pdf_content, "DIRECCION", "\nCUPS")
            cups = get_content_between_words(pdf_content, "CUPS", "\nTOTAL")
            asesor = get_content_between_words(pdf_content, "ASESOR ENERGETICO\n", "\n")

            data["ARCHIVO"].append(pdf_filename)
            data["NOMBRE/RAZÓN"].append(nombre_razon)
            data["DIRECCION"].append(direccion)
            data["CUPS"].append(cups)
            data["ASESOR ENERGETICO"].append(asesor)

        #3.0/6.x actual        
        elif anual == -1 and actual != -1 and dospuntozero == -1:
            nombre_razon = get_content_between_words(pdf_content, "NOMBRE/RAZÓN", "DIRECCION")
            direccion = get_content_between_words(pdf_content, "DIRECCION", "\nCOMPAÑIA")
            cups = get_content_between_words(pdf_content, "CUPS", "DATOS")
            asesor = get_content_between_words(pdf_content, "ASESOR ENERGETICO\n", "\n")

            data["ARCHIVO"].append(pdf_filename)
            data["NOMBRE/RAZÓN"].append(nombre_razon)
            data["DIRECCION"].append(direccion)
            data["CUPS"].append(cups)
            data["ASESOR ENERGETICO"].append(asesor)

        #3.0/6.x anual
        elif anual != -1 and actual == -1 and dospuntozero == -1:
            nombre_razon = get_content_between_words(pdf_content, "NOMBRE/RAZÓN", "DIRECCION")
            direccion = get_content_between_words(pdf_content, "DIRECCION", "\nTOTAL")
            cups = get_content_between_words(pdf_content, "CUPS", "DATOS")
            asesor = get_content_between_words(pdf_content, "ASESOR ENERGETICO\n", "\n")

            data["ARCHIVO"].append(pdf_filename)
            data["NOMBRE/RAZÓN"].append(nombre_razon)
            data["DIRECCION"].append(direccion)
            data["CUPS"].append(cups)
            data["ASESOR ENERGETICO"].append(asesor)
        
            
    logging.info(f"PDF Content:\n{pdf_content}"
            f"fecha_de_envio: {fecha_de_envio}"
            #f"data: {data}"
            )

    return data

def save_data_to_blob(data, blob_client):

    #download report
    blob_data = blob_client.download_blob()
    csv_data = blob_data.readall()

    df_report = pd.read_csv(BytesIO(csv_data))
    
    # Convert data to DataFrame
    new_data = pd.DataFrame(data)
    
    # Add data to report
    df = pd.concat([df_report, new_data], ignore_index=True)
    
    # Convert DataFrame to CSV in-memory
    csv_data = df.to_csv(index=False)
    csv_data_bytes = csv_data.encode('utf-8')

    # Upload CSV to Blob Storage
    blob_client.upload_blob(csv_data_bytes, overwrite=True)

"""    # Convert DataFrame to Parquet in-memory
    table = pa.Table.from_pandas(df)
    parquet_data = BytesIO()
    pq.write_table(table, parquet_data)

    # Upload Parquet to Blob Storage
    blob_client.upload_blob(parquet_data.getvalue())"""



app = func.FunctionApp()
@app.blob_trigger(arg_name="myblob", path="raw/{name}.pdf", connection="BlobStorageConnectionString")

def blob_trigger(myblob: func.InputStream):
    pdf_filename = myblob.name[4:]
    logging.info(f"Python blob trigger function processed blob. "
                f"Name: {myblob.name}. "
                f"Blob Size: {myblob.length} bytes."
                f"Pdf: {pdf_filename}")
    
    connection_string = os.environ["BlobStorageConnectionString"]

    # Create a BlobServiceClient
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)

    # Create a BlobClient to interact with a specific blob
    blob_client_raw = blob_service_client.get_blob_client(container="raw", blob=pdf_filename)

    # Get pdfblob content
    pdf_content = read_pdf_from_blob(blob_client_raw)

    # Delete pdf blob
    blob_client_raw.delete_blob()
    
    # creating dataframe
    data = building_data(pdf_filename,pdf_content)

    logging.info(f"Pdf: {data}")
    
    blob_client_staging = blob_service_client.get_blob_client(container="staging", blob="report.csv")
    
    # add data to report
    save_data_to_blob(data, blob_client_staging)



