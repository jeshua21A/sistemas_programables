# Implementación de librerias
import network
import time
from machine import UART
from umqtt.simple import MQTTClient
import urequests
from micropyGPS import MicropyGPS

# Parámetros de configuración Wi-Fi
ssid = "Waos"
password = "00000009"

# Parámetros de configuración MQTT Dash
broker_MQTT = "broker.hivemq.com"
Topic_Latitud = b"practica/gps/latitud"
Topic_Longitud = b"practica/gps/longitud"
Topic_Altitud = b"practica/gps/altitud"
Topic_Velocidad = b"practica/gps/velocidad"
Topic_Fecha = b"practica/gps/fecha"
Topic_Hora = b"practica/gps/hora"

# Parámetros de configuración GPS
# Le decimos a MicropyGPS que use el formato 'dd' (Grados decimales)
gps = MicropyGPS(location_formatting='dd')
puerto_uart = UART(2, baudrate=9600, tx=17, rx=16, timeout=10)

# URL de Firebase para conectar la base de datos
Firebase_URL = "https://mapa-interactivo-548d3-default-rtdb.firebaseio.com/.json"

def conectar_Wifi(ssid, password):
    """
    Función para conectarse a una red Wi-Fi.
    :param ssid: Nombre de la red Wi-Fi
    :param password: Contraseña de la red Wi-Fi
    :return: Dirección IP asignada al dispositivo
    """
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    
    print("Conectando a la red Wifi...")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.5)
        
    print("\nConexion exitosa")
    print("Direccion asignada", wlan.ifconfig()[0])
    

def enviar_datos_firebase(latitud, longitud, altitud, velocidad, tiempo, fecha):
    # Diccionario de datos en forma de estructura anidada para luego convertirla
    # en un formato JSON para enviar a Firebase (el fin es organizar datos de forma clara)
    datos = {
        "GPS": {
            "Altitud": altitud,
            "Latitud": latitud,
            "Longitud": longitud,
            "Velocidad": velocidad,
            "Hora": tiempo,
            "Fecha": fecha
        }
    }
    
    try:
        # Actualizamos solo las claves que se envian dentro del formato JSON
        response = urequests.patch(Firebase_URL, json=datos)
        # Mensaje de verificación para comprobar que los datos se enviaron correctamente
        print("Enviando datos: ", response.status_code)
        # Cerramos la conexión para liberar memoria de microcontrolador
        response.close()
    except Exception as ex:
        print("Error al enviar sensores: ", ex)

def main():
    # Crear cliente MQTT
    cliente = MQTTClient("ESP32-CAM", broker_MQTT)
    # Conectar al servidor MQTT
    cliente.connect()
    # Imprimir información de conexión
    print("Conectando cliente al Broker MQTT: ", broker_MQTT)
    
    """
    Bucle infinito para leer continuamente los datos del sensor GPS,
    enviar (por medio del Wifi) los datos al servidor MQTT para reflejarlos
    en la aplicación MQTT Dash y registrarlos en la base de datos de Firebase
    para permitir que el mapa interactivo (creado por un archivo de html con
    con funciones de javascript) pueda recibirlos por parte de la parametros
    de configuración de Firebase.
    """
    while True:
        # Leer para determinar que todos los bytes esten disponibles en el buffer UART
        if puerto_uart.any():
            # Leer el bloque de datos (bytes)
            datos_uart = puerto_uart.read()
            if datos_uart:
                try:
                    # Procesar cada byte por byte con MicropyGPS
                    for byte in datos_uart:
                        # Con el método update se devuelve el nombre de la sentencia
                        # (ejemplo 'GPGGA') si se procesa
                        nombre_sentencia = gps.update(chr(byte))
                    
                    """
                    La verificación y la publicación se actualizan cada vez que se procesa una sentencia.
                    La variable gps.valid se actualiza con sentencias RMC/GGA-GSA (gps.fix_type)
                    y por lo tanto es mejor verificar el fix porque permite un cálculo de posición
                    satelital valido al asegurar que todos los datos internos son los más recientes
                    y válidos, además de evitar datos vacíos que .startswith() deja.
                    """
                    
                    if gps.fix_type >= 2: # Posición horizontal (Latitud y Longitud) válida
                        # Extracción de los datos específicos
                        
                        # Datos de posición y velocidad
                        latitud = gps.latitude[0]
                        # Modificación del signo cuando son coordenadas negativas
                        if (gps.longitude[1]) in ['S', 'W']:
                            longitud = -(gps.longitude[0])
                        else:
                            longitud = gps.longitude[0]
                        altitud = gps.altitude
                        velocidad = gps.speed[2]
                        
                        # Datos de tiempo y fecha
                        # Fecha en formato (MM/DD/YY)
                        fecha = gps.date_string(formatting='s_mdy', century='20')
                        # Hora en formato (HH:MM:SS)
                        hora = f"{gps.timestamp[0]:02}:{gps.timestamp[1]:02}:{int(gps.timestamp[2]):02}"
                        
                        # Impresión para verificar que los valores sean correctos
                        print("\n*** FIX VALIDO ENCONTRADO ***")
                        print(f"Latitud: {latitud}, Longitud: {longitud}, Altitud: {altitud} m")
                        print(f"Velocidad: {velocidad} Km/h")
                        print(f"Fecha: {fecha}, Hora: {hora}s")
                        
                        # Publicación de los datos al servidor MQTT
                        cliente.publish(Topic_Latitud, str(latitud))
                        cliente.publish(Topic_Longitud, str(longitud))
                        cliente.publish(Topic_Altitud, str(altitud))
                        cliente.publish(Topic_Velocidad, str(velocidad))                        
                        cliente.publish(Topic_Fecha, str(fecha))
                        cliente.publish(Topic_Hora, str(hora))
                        
                        # Llamamos a la función para obtener los datos y registrarlos a la base de datos de Firebase
                        enviar_datos_firebase(latitud, longitud, altitud, velocidad, fecha, hora)
                        
                    elif gps.fix_type == 1:
                        print("Buscando señal GPS....(No fix)")
                except Exception as ex:
                    print("Error en: ", ex)
        # Instrucción de retardo para no saturar la CPU
        time.sleep(0.5)

# Función para ejecutar las principales funciones del programa final
if __name__ == '__main__':
    conectar_Wifi(ssid, password)
    main()