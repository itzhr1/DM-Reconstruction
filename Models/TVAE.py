import numpy as np
import tensorflow as tf
from tensorflow.keras import layers
from tqdm.notebook import tqdm
from Utils.QMetrics import trace_loss

class Sampling(layers.Layer):
  """Uses (z_mean, z_log_var) to sample z, the vector encoding a digit."""

  def call(self, inputs):
    z_mean, z_log_var = inputs
    batch = tf.shape(z_mean)[0]
    dim = tf.shape(z_mean)[1]
    epsilon = tf.keras.backend.random_normal(shape=(batch, dim))
    return z_mean + tf.exp(0.5 * z_log_var) * epsilon


class Encoder(layers.Layer):
  """Maps Input to a triplet (z_mean, z_log_var, z)."""

  def __init__(self,
               latent_dim=32,
               intermediate_dim=64,
               dtype='float64',
               **kwargs):
    
    super(Encoder, self).__init__(**kwargs)
    self.dense_proj = []
    for i in intermediate_dim:
      self.dense_proj.append(layers.Dense(i,
                                          activation=tf.nn.relu))
    

    self.dense_mean = layers.Dense(latent_dim)
    self.dense_log_var = layers.Dense(latent_dim)
    self.sampling = Sampling()

  def call(self, inputs):
    x = self.dense_proj[0](inputs)
    
    for lay in self.dense_proj[1:]:
      x = lay(x)
    
    z_mean = self.dense_mean(x)
    z_log_var = self.dense_log_var(x)
    z = self.sampling((z_mean, z_log_var))
    return z_mean, z_log_var, z

class Decoder(layers.Layer):
  """Converts z, the encoded digit vector, back into a readable digit."""

  def __init__(self,
               original_dim,
               intermediate_dim=64,               
               **kwargs):
    super(Decoder, self).__init__(**kwargs)

    self.dense_proj = []
    for i in intermediate_dim:
      self.dense_proj.append(layers.Dense(i,
                                          activation=tf.nn.relu))
    
    self.dense_output = layers.Dense(original_dim)

  def call(self, inputs):
    x = self.dense_proj[0](inputs)
    
    for lay in self.dense_proj[1:]:
      x = lay(x)

    return self.dense_output(x)


class TraceVAE(tf.keras.Model):
  """Combines the encoder and decoder into an end-to-end model for training."""

  def __init__(self,
               original_dim,
               intermediate_dim,
               latent_dim,               
               **kwargs):
    
    super(TraceVAE, self).__init__(**kwargs)
    self.original_dim = original_dim
    self.encoder = Encoder(latent_dim=latent_dim,
                           intermediate_dim=intermediate_dim)
    self.decoder = Decoder(original_dim, 
                           intermediate_dim=intermediate_dim)    

  def call(self, inputs):
    z_mean, z_log_var, z = self.encoder(inputs)
    reconstructed = self.decoder(z)
    # Add KL divergence regularization loss.
    kl_loss = - 0.5 * tf.reduce_mean(
        z_log_var - tf.square(z_mean) - tf.exp(z_log_var) + 1)    
    self.add_loss(kl_loss)
    return reconstructed

  def training_step(self, x, r_loss, beta):
    """Training step for the VAE.
  
    Parameters
    -------------------------------------------
    x: Data
    VAE(tf.keras.Model): Variational Autoencoder model. 
    optimizer(tf.keras.optimizer): Optimizer used.  
    r_loss(float): Parameter controlling reconstruction loss.
    beta(float): Parameter controlling the KL divergence.

    Return:
    Loss(float): Loss value of the training step.

    """
    with tf.GradientTape() as tape:
      reconstructed = self(x)#, training=True)  # Compute input reconstruction.
      # Compute loss.
      loss = trace_loss(x, reconstructed)
      kl = sum(self.losses)
      loss = r_loss * loss + beta*kl  
    
    # Update the weights of the VAE.
    grads = tape.gradient(loss, self.trainable_weights)
    self.optimizer.apply_gradients(zip(grads, self.trainable_weights))    
    return loss

  def training(self, dataset, 
             epochs, r_loss, beta,              
             Plotter=None):
    """ Training of the Variational Autoencoder for a 
    tensorflow.dataset.

    Parameters
    -------------------------------------------
    dataset(tf.data.Dataset): Dataset of the data.
    VAE(tf.keras.Model): Variational Autoencoder model.
    epochs(int): Number of epochs.
    r_loss(float): Parameter controlling reconstruction loss.
    beta(float): Parameter controlling the KL divergence.  
    Plotter(object): Plotter object to show how the training is
                    going (Default=None).

    """

    losses = []
    epochs = range(epochs)

    for i in tqdm(epochs, desc='Epochs'):
      losses_epochs = []
      for step, x in enumerate(dataset):

        loss = self.training_step(x, r_loss, beta)
  
        # Logging.
        losses_epochs.append(float(loss))
      losses.append(np.mean(losses_epochs))
    
      if Plotter != None:
        Plotter.plot(losses)

    return losses 