-- Inserção das 6 Máquinas Injetoras
INSERT INTO maquinas (numero_maquina, descricao, cavidades, ciclo_padrao) VALUES
(1, 'Injetora 01 - Peça A', 4, 18.5),
(2, 'Injetora 02 - Peça B', 2, 22.0),
(3, 'Injetora 03 - Peça C', 8, 15.0),
(4, 'Injetora 04 - Peça D', 4, 20.0),
(5, 'Injetora 05 - Peça E', 1, 30.0),
(6, 'Injetora 06 - Peça F', 6, 16.5)
ON CONFLICT (numero_maquina) DO NOTHING;