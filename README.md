**<h1>XSCRAP: Scrapper distribuido</h1>**
---

_Equipo:_
- _Gabriel Hernández Rodríguez C411_
- _Deborah Famadas Rodríguez C412_
- _David Manuel García Aguilera C411_


**<h1>Tabla de Contenidos</h1>**
- [1. Arquitectura](#1-arquitectura)
  - [1.1 Balanceo de Carga](#11-balanceo-de-carga)
  - [1.2 Tolerancia a fallos](#12-tolerancia-a-fallos)
    - [1.2.1 Eventos de primer tipo](#121-eventos-de-primer-tipo)
      - [1.2.1.1 Capa Estática](#1211-capa-estática)
      - [1.2.1.2 Capa Dinámica](#1212-capa-dinámica)
    - [1.2.2 Eventos de segundo tipo](#122-eventos-de-segundo-tipo)
  - [1.3 Consideraciones en Rendimiento](#13-consideraciones-en-rendimiento)
  - [1.4 Extensibilidad](#14-extensibilidad)
  - [1.5 Tecnología Utilizada](#15-tecnología-utilizada)
- [2. Inicialización del Sistema](#2-inicialización-del-sistema)
  - [2.1 Instalación](#21-instalación)
  - [2.2 Configuración](#22-configuración)
  - [Ejecución](#ejecución)

# 1. Arquitectura
La arquitectura base utilizada en el proyecto es MAster-Slave, donde hay un controlador centralizado(Master) que contien la mayor parte de la lógica y los slave se limitan a comunicarse con este para realizar determinados trabajos.

En el sistema este master es llamado Dispatcher ya que su principal trabajo es manejar las urls pendientes a recuperar su contenido. Para apoyarse utiliza un nodo Cache que funciona como caché(por supuesto) y como message broker.

Los slaves que se conectan a él pueden ser clientes o trabajadores. Los clientes son aquellos que encolan tareas, en este caso los clientes son un servidor con una APIRest. Los trabajadores son los que procesan las tareas, es decir, hacen las peticiones HTTP para obtener el contenido de las páginas.

De esta forma se definen 4 roles para cada nodo que forma parte del sistema:
1. Dispatcher (master)
2. Cache (también Message Broker)
3. API (slave/cliente)
4. Worker (slave/trabajador)

## 1.1 Balanceo de Carga

Los roles API y Worker tienen conocimiento del nodo Dispatcher con el que interactúan, no ocurriendo esto en el sentido contrario, es decir, estos se preconfiguran y conocen la dirección en la que se encuentra este, realizan llamadas RPC que se encargan de enviar trabajos y esperar resultados, y esperar trabajo y enviar resultados respectivamente. Este esquema de trabajo hace que el balanceo de carga ocurra de manera natural, una vez los trabajadores ya no estén realizando otra tarea, disminuyendo la carga de asignación de tareas en el master.

Los trabajadores siempre que no estén realizando trabajo alguno se mantienen pidiendo trabajo al master, de la misma forma que la API se mantiene pidiendo el contenido de las urls de una request.

## 1.2 Tolerancia a fallos

Las técnicas particulares implementadas para tolerancia a fallos en este sistema se clasifican en 2 categorías según el tipo de conflicto al que atienden, los conflictos que impiden el procesamiento de urls y los conflictos que afectan el procesamiento actual de estas. Por ejemplo, tienen distintas implicaciones los siguientes eventos:

- Una API al querer enviar urls para procesar se percata que no tiene dispatcher al que conectarse debido a que este dejó de operar. (1er tipo)
- Una API envió urls para procesar al dispatcher y durante el trabajo de los trabajadores uno de estos dejó de funcionar dejando el procesado de esta url a medias. (2do tipo)

Estos eventos hacen que nos tengamos que alejar de un método clásico de programación donde cada componente actúa de una forma determinista y opera siempre de manera correcta en el proceso general. Con el uso de RPC estos componentes se encuentran en procesos distintos y quizás en computadoras distintas, siendo afectados por disímiles sucesos desde problemas en la asignación de recursos en el sistema operativo, hasta desconexión de red, destrucción de la computadora remota en la que se ejecuta ese componente o mordedura del cable de red entre ambos nodos por un ratón, pez o operador hambriento.

### 1.2.1 Eventos de primer tipo

Para manejar eventos del primer tipo se utilizan dos capas de resolución de componentes, la capa estática y la capa dinámica.

#### 1.2.1.1 Capa Estática

La capa estática constituye de una serie de configuraciones que permiten al sistema conectarse en un inicio de la manera deseada. Estas se explicaran con más detalle en [2.2](#22-configuración). Este sistema está pensado para que se utilicen otras tecnologías de automatización que permitan inicializar cada nodo de la manera deseada y con la configuración deseada, permitiendo que incluso ante fallos del sistema, este se comporte de manera fácil de controlar, predecir y poder actuar en consideración.

Esta capa estática se basa en la preconfiguración de direcciones de respaldo a las que conectarse en caso de que el Dispatcher, que es el centro operacional de una instancia de este sistema, deje de operar por completo. Se centra en atender a este rol específicamente por dos razones: primero, es el principal cuello de botella del sistema y además su componente más débil; y segundo, como se decía anteriormente, los nodos slave necesitan conocer la dirección en que este se encuentra para operar correctamente.

Una vez que el dispatcher principal para el que se configuraron deja de funcionar la API y los Workers entonces comienzan un proceso de resolución del nuevo dispatcher que sigue estás reglas por orden.

1. Comprueba la configuración **MBB**(*Must be brave*). Si la cantidad de intentos está configurada en 0 el nodo se mantiene intentando reconectar con el Dispatcher hasta lograrlo.
2. La cantidad de intentos es mayor que 0, entonces el nodo intentará conectar esa cantidad de veces con el dispatcher principal configurado con determinado tiempo de espera entre un intento y otro.
3. Superó la cantidad de intentos establecida, entonces comprueba los Dispatcher de **Backup** configurados. Existen dos tipos de dispatcher de backup configurados:
    + Una dirección y puerto brindados por el Dispatcher principal. Al conectar, el dispatcher principal tenía configurado un backup y se lo comunicó a todos aquellos slaves que interactuaron con él. Este tiene la primera prioridad al buscar un Dispatcher Backup.
    + Una dirección y puerto brindados por la configuración propia del nodo. Esta no tiene prioridad y solo se utiliza en caso de que el Dispatcher principal no tenga configurada una o la comunicación con este no se logró ni una sola vez.
4. En caso de no encontrarse respaldo o no poder conectar con este el nodo se queda huérfano y procede de manera distinta según su rol. En caso de ser un Worker, este deja de funcionar automáticamente. En el caso de la API entonces se actúa de manera dinámica como se explicará más adelante.

Si un nodo se conecta a un dispatcher de respaldo este siempre sabrá que es de respaldo y cuando este falle buscará al principal e iniciará el mismo proceso inicial en caso de no funcionar. Un caso especial es cuando el Dispatcher de backup tiene configurado un Dispatcher de backup, entonces el nodo tomará este como su nuevo backup en caso de necesitar resolver nuevamente la conexión.

#### 1.2.1.2 Capa Dinámica

La capa dinámica se encarga de cubrir las debilidades que deja la estática. ¿Si un slave no logra conectar con ningún Dispatcher que puede hacer? ¿Qué pasa si un dispatcher no tiene trabajadores conectados a él o caché a la cual conectarse?

Lograr que el sistema "se mantenga funcionando" no es más que hacer que siga atendiendo peticiones de los clientes y procesándolas. Si un worker deja de funcionar no implica mucho a no ser que solo exista uno, otro caso distinto es si el Dispatcher o la cache dejara de funcionar.

Para contrarrestar esto el dispatcher es capaz de crear(**Spawn**) nodos de cache y trabajadores en la misma máquina en la que este se ejecuta. Para los trabajadores posee un comportamiento que registra los accesos de estos y así poder estimar la cantidad de workers conectados a él, una vez que hace más de determinado tiempo que un Worker no se conecta a él, asume que no está funcionando. Una vez que llega una url para ser procesada, si la cantidad de trabajadores estimada está por debajo de cierto umbral comienza a crear nodos Workers y conectarlos a él .

De manera similar ocurre con la cache, en caso de perder conexión con la cache establecida, o esta estar ausente en un principio crea un nodo con este rol y se conecta a él.

La API por su parte es el componente que está en contacto con el usuario, así que también necesita un nodo dispatcher a toda costa, de la misma manera que este necesita un nodo cache. Una vez que pasa la capa estática sin encontrar Dispatcher el nodo API crea un nodo cache localmente, este a su vez se encontrará sin Workers y sin cache y por tanto creará estos nodos localmente, encontrándose un sistema completo localmente en la máquina que contiene la API.

Los nodos **Spawn** no poseen fácil acceso y están pensados como último recurso, una vez termina el proceso del nodo que los creó los procesos de estos también terminan.

En caso de que el nodo API deje de funcionar queda por parte de quien utilice el sistema utilizar protocolos de resolución de DNS que permitan reconectar con otro IP y por tanto otro nodo API y trabajar esto en los clientes.

### 1.2.2 Eventos de segundo tipo

Para evitar el mal funcionamiento del sistema ante interrupciones en el procesado de una url se propone una arquitectura ligera que dependa mínimamente de datos almacenados aún si estos no poseen persistencia (ante un reinicio del sistema se pierden).

Una vez que el nodo API atiende una request, este mantiene la lista de las urls que se piden y recorre una por una para brindarle el contenido a su cliente por streaming. Por cada url se comunica de manera "insistente" con el Dispatcher pidiendo resultados, lo cual se realiza enviando la url de la cual se esperan resultados.

Cuando el dispatcher recibe una url, no importa si es primera vez o si es solo la API siendo insistente, él intenta encolarla para su procesado, esto permite que en caso de perder la url sin haber recuperado su contenido esta vuelva al sistema si aún el cliente no ha terminado con ella. De esta forma *no importa si desaparecen todos los trabajadores, si la cache se borra por completo, o si además deja de funcionar el Dispatcher, la url siempre será procesada en algún momento*.

## 1.3 Consideraciones en Rendimiento

Por lo mencionado anteriormente pudiera pensarse que el sistema carga de peticiones al dispatcher innecesariamente y además asigna una misma url demasiadas veces a los trabajadores, pero el sistema está centrado en rendimiento y para evitar esto se implementan varias técnicas.

Para evitar cargar al Dispatcher con peticiones innecesarias se utiliza un sistema de espera en los nodos slave que, cuando el resultado de la comunicación con este no sea satisfactorio, se procede a esperar un tiempo antes de la próximo RPC que va en aumento según el número de llamadas insatisfactorias continuas.

Para evitar sobre-procesar una misma url se declara una regla y es que en la cola a procesar(cola de pendientes), no puede estar una misma url dos veces, para esto, una vez que entra una url a la cola se almacena en la cache como pendiente y se retira de este estado una vez que sale de la cola y se le asigna a un trabajador.

Aún con este método, puede darse el caso en el que la url ya se procesó, está en la cola de pendiente, y todos los trabajadores la están procesando; pero esta situación es altamente improbable ya que tienen que cumplirse muchas condiciones para llegar a este punto, y en la mayoría de los casos, donde las url a recuperar su contenidos son muchísimas, esto no debe ocurrir.

Para acelerar las respuestas del sistema además se almacenan los resultados de los urls al procesarlas, lo que permite dar estas como respuesta al cliente sin enviarlas necesariamente a procesar a los trabajadores, aún así las urls que al procesar tengan respuesta que no sea satisfactoria se le da el resultado como respuesta al cliente pero se envían a procesar de nuevo en caso de que este resultado pueda cambiar por ser un error temporal, al igual que de manera aleatoria algunas url con respuesta 200 que pudieran haber cambiado.

## 1.4 Extensibilidad

Este sistema solo requiere 1 nodo de cada rol para funcionar, y como mínimo una sola computadora. El sistema puede extenderse añadiendo más trabajadores para que las urls se procesen con mayor mayor fluidez y, además, sencillamente poniendo en funcionamiento otra instancia independiente del sistema, permitiendo que los fallos no escalen entre instancias.

Una instancia puede ser considerada como un nodo Dispatcher, un nodo Cache, $n$ nodos API y $m$ Workers que se comunican entre si. Pueden funcionar dos instancias a través de las mismas máquinas permitiendo diseños del sistema extremadamente abiertos. Se pueden diseñar por configuración respuestas a fallos sin salir de la capa estática que conecten como backup múltiples Dispatchers de manera circular y además se puede hacer que dos instancias utilicen la misma cache, balanceando la carga entre ambas, incluida la lógica de procesamiento del Dispatcher.

## 1.5 Tecnología Utilizada

El sistema está programado en Python. Para implementar RPC y garantizar comunicación entre nodos se utiliza la librería Pyro5 de manera límitada, ya que se realizan conexiones directas y no se utilizan las funcionalidades que provee de Name Server, los nodos Dispatcher y Cache son objetos de Pyro5 que se utilizan como una sola instancia del objeto por Daemon.

Para facilitar la implementación del CLI base de la app que permite escoger el rol que se ejecuta se utiliza la librería Fire, y el nodo API es un servidor sobre el framework FastAPI. Este último da respuesta a las peticiones del endpoint `/scrap` haciendo un streaming por SSE(*Server sent events*), el cual siempre que mantenga el cliente la conexión abierta puede dar los contenidos de las urls a medida que se van procesando. La API brinda además un endpoint para eliminar la cache de determinadas urls(`/reset`).

# 2. Inicialización del Sistema
## 2.1 Instalación

Para poder ejecutar un nodo del sistema solo es necesario instalar Python version 3.10 o mayor y las librerías necesarias, las cuales están referenciadas en el archivo `requirements.txt` adjunto.

## 2.2 Configuración

La configuración de la aplicación se realiza a través de variables de entorno y está pensada para tener implicaciones en el funcionamiento de una instancia del sistema de manera que pueda ser una parte compartida por cada nodo de esta.

La siguiente tabla muestra cada variable de entorno, el valor por defecto que se asume en caso de no definirse y la implicación que tiene en el funcionamiento de cada rol.

| Variable                 | Valor por defecto                                                                                                       | API                                                                                                             | Dispatcher                                                                                                                                                                                               | Cache                                                                          | Worker                                                                                                          |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `HOSTNAME`               | El nombre de la máquina que lo está ejecutando. Resultado de `socket.gethostname()`                                     | En caso de no definirse API_HOST se utiliza como dirección de hosting                                           | En caso de no definirse DISPATCHER se utiliza como dirección de hosting                                                                                                                                  | En caso de no definirse CACHE_SERVER_HOST se utiliza como dirección de hosting |                                                                                                                 |
| `HOSTPORT`               | 8000                                                                                                                    | En caso de no definirse API_PORT se utiliza como puerto de hosting                                              | En caso de no definirse DISPATCHER_PORT se utiliza como puerto de hosting                                                                                                                                | En caso de no definirse CACHE_SERVER_PORT se utiliza como puerto de hosting    |                                                                                                                 |
| `DISPATCHER`             | El valor en `HOSTNAME` o su valor por defecto                                                                           | Determina la dirección del Dispatcher principal al que conectarse                                               | Se utiliza como dirección de hosting                                                                                                                                                                     |                                                                                | Determina la dirección del Dispatcher principal al que conectarse                                               |
| `DISPATCHER_PORT`        | El valor en `HOSTPORT` o su valor por defecto                                                                           | Determina el puerto del Dispatcher principal al que conectarse                                                  | Se utiliza como puerto de hosting                                                                                                                                                                        |                                                                                | Determina el puerto del dispatcher principal al que conectarse                                                  |
| `API_HOST`               | El valor de `HOSTNAME` o su valor por defecto                                                                           | Se utiliza como dirección de hosting                                                                            |                                                                                                                                                                                                          |                                                                                |                                                                                                                 |
| `API_PORT`               | El valor de `HOSTPORT` o 6900                                                                                           | Se utiliza como puerto de hosting                                                                               |                                                                                                                                                                                                          |                                                                                |                                                                                                                 |
| `CACHE_SERVER_URL`       | El valor por defecto es construido a partir de `CACHE_SERVER_HOST` y `CACHE_SERVER_PORT` con el formato de URIs de Pyro |                                                                                                                 | Se utiliza como URI exacta para conectar con el objeto de Pyro que funciona como cache                                                                                                                   |                                                                                |                                                                                                                 |
| `CACHE_SERVER_HOST`      | El valor de `HOSTNAME` o su valor por defecto                                                                           |                                                                                                                 | En caso de no estar definido `CACHE_SERVER_URL` define la dirección en la que se buscará la cache                                                                                                        | Se utiliza como dirección de hosting                                           |                                                                                                                 |
| `CACHE_SERVER_PORT`      | El valor de `HOSTPORT` o 6380                                                                                           |                                                                                                                 | En el caso de no estar definido `CACHE_SERVER_URL` define el puerto en el que se buscará la cache                                                                                                        | Se utiliza como puerto de hosting                                              |                                                                                                                 |
| `BACKUP_DISPATCHER`      | En caso de estar definido `BACKUP_DISPATCHER_PORT` `HOSTNAME` o su valor por defecto, en caso contrario `None`          | Se utiliza como dirección del Dispatcher de backup si no brinda otro el Dispatcher principal                    | Define la dirección del Dispatcher de repuesto que este comunica a los slaves que se conecten a él                                                                                                       |                                                                                | Se utiliza como dirección del Dispatcher de backup si no brinda otro el Dispatcher principal                    |
| `BACKUP_DISPATCHER_PORT` | En caso de estar definido `BACKUP_DISPATCHER` `HOSTPORT` o su valor por defecto, en caso contrario `None`               | Se utiliza como puerto del Dispatcher de backup si no brinda otro el Dispatcher principal                       | Define el puerto del Dispatcher de repuesto que este comunica a los slaves que se conecten a él                                                                                                          |                                                                                | Se utiliza como puerto del Dispatcher de backup si no brinda otro el Dispatcher principal                       |
| `WORKER_TIMEOUT`         | 60 segundos                                                                                                             |                                                                                                                 | Número se segundos que deben pasar desde la última comunicación para que el Dispatcher considere que un trabajador está desconectado.                                                                    |                                                                                |                                                                                                                 |
| `WORKER_AMOUNT`          | 3                                                                                                                       |                                                                                                                 | Número mínimo de workers que el Dispatcher considera que debería tener para funcionar correctamente. Si la cantidad estimada de workers en servicio está por debajo de este número se crean trabajadores |                                                                                |                                                                                                                 |
| `MBB_RETRIES`            | 5                                                                                                                       | Intentos de conexión con el Dispatcher principal una vez que deja de operar antes de buscar Backup              |                                                                                                                                                                                                          |                                                                                | Intentos de conexión con el Dispatcher principal una vez que deja de operar antes de buscar Backup              |
| `MBB_TIME`               | 1                                                                                                                       | Tiempo entre intentos de conexión con el Dispatcher principal una vez que deja de operar antes de buscar Backup |                                                                                                                                                                                                          |                                                                                | Tiempo entre intentos de conexión con el Dispatcher principal una vez que deja de operar antes de buscar Backup |
| `CACHE_MAX_SIZE`         | 100 000                                                                                                                 |                                                                                                                 |                                                                                                                                                                                                          | Cantidad de urls máxima que guardará la cache                                  |                                                                                                                 |
| `PENDING_QUEUE_MAXSIZE`  | 10 000                                                                                                                  |                                                                                                                 |                                                                                                                                                                                                          | Cantidad de urls máxima que guardará la cola de pendientes                     |                                                                                                                 |
## Ejecución

Para ejecutar un nodo del sistema debe primero configurar las variables de entorno de la manera deseada y luego llamar al script principal de la siguiente forma:
```shell
python xscrap.py <role>
```
